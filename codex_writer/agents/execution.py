import json
from pathlib import Path

from codex_writer.agents.privacy import can_send_external, load_privacy_from_env
from codex_writer.agents.providers import (
    create_provider,
    is_external_provider,
    provider_config_errors,
)
from codex_writer.agents.router import load_project_router, route_agent
from codex_writer.core.config import load_settings


PRODUCTION_AGENTS = ("planning_agent", "draft_agent")


def resolve_agent_provider(project_root: Path, agent: str, provider_override: str = "",
                           require_external: bool = False, input_kind: str = "context_pack",
                           input_chars: int = 0) -> dict:
    router = load_project_router(project_root)
    route = dict(route_agent(router, agent))
    if provider_override:
        route["provider"] = provider_override
    provider = route.get("provider", "codex")
    model = route.get("model", "default")
    settings = load_settings()
    errors = []

    if require_external and not is_external_provider(provider):
        errors.append({
            "code": "PRODUCTION_PROVIDER_REQUIRED",
            "message": f"{agent} must route to an external provider in production mode",
            "blocking": True,
        })

    if is_external_provider(provider):
        policy = load_privacy_from_env()
        if not can_send_external(policy, input_kind=input_kind, chars=input_chars):
            errors.append({
                "code": "PRIVACY_BLOCK",
                "message": "Privacy policy blocks external model calls",
                "blocking": True,
            })
        errors.extend(provider_config_errors(provider, settings, model))

    exit_code = _exit_code_for_errors(errors)
    provider_obj = None
    if not errors:
        provider_obj = create_provider(provider, model=model, settings=settings)

    return {
        "agent": agent,
        "route": route,
        "provider": provider,
        "model": model,
        "provider_obj": provider_obj,
        "errors": errors,
        "exit_code": exit_code,
    }


def production_preflight(project_root: Path, input_chars: int = 0) -> dict:
    checks = []
    errors = []
    for agent in PRODUCTION_AGENTS:
        resolution = resolve_agent_provider(
            project_root,
            agent,
            require_external=True,
            input_kind="context_pack",
            input_chars=input_chars,
        )
        checks.append({
            "agent": agent,
            "route": resolution["route"],
            "ready": not resolution["errors"],
            "errors": resolution["errors"],
        })
        errors.extend(resolution["errors"])
    return {"checks": checks, "errors": errors, "exit_code": _exit_code_for_errors(errors)}


def provider_result_error(result: dict, code: str = "PROVIDER_FAILURE") -> list[dict]:
    if result.get("error"):
        return [{"code": code, "message": str(result["error"]), "blocking": True}]
    return []


def payload_chars(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False))


def _exit_code_for_errors(errors: list[dict]) -> int:
    if not errors:
        return 0
    if any(error.get("code") == "PRIVACY_BLOCK" for error in errors):
        return 4
    return 5
