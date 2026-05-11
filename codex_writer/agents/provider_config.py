from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_writer.agents.providers import OPENAI_COMPATIBLE
from codex_writer.agents.router import load_project_router
from codex_writer.core.config import Settings, load_settings
from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import agent_router_path, provider_config_path


PROVIDER_CONFIG_SCHEMA = "codex-writer/provider-config/v1"
PRODUCTION_AGENT_NAMES = ("planning_agent", "draft_agent", "extract_agent")
OPENAI_COMPATIBLE_API_KEY_ENV = "CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY"

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "preset": "openai",
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": "https://api.openai.com/v1",
        "model": "",
        "timeout": 60.0,
        "max_tokens": 4096,
    },
    "deepseek": {
        "preset": "deepseek",
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": "https://api.deepseek.com/v1",
        "model": "",
        "timeout": 60.0,
        "max_tokens": 4096,
    },
    "qwen": {
        "preset": "qwen",
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "",
        "timeout": 60.0,
        "max_tokens": 4096,
    },
    "custom": {
        "preset": "custom",
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": "",
        "model": "",
        "timeout": 60.0,
        "max_tokens": 4096,
    },
}


def default_provider_config() -> dict:
    return {
        "schema_version": PROVIDER_CONFIG_SCHEMA,
        "provider": {
            "preset": "",
            "provider": OPENAI_COMPATIBLE,
            "protocol": "openai-compatible",
            "base_url": "",
            "model": "",
            "timeout": 60.0,
            "max_tokens": 4096,
        },
        "updated_at": "",
    }


def load_provider_config(project_root: Path) -> dict:
    path = provider_config_path(project_root)
    if not path.exists():
        return default_provider_config()
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError):
        return default_provider_config()
    if not isinstance(data, dict):
        return default_provider_config()
    provider = data.get("provider")
    if not isinstance(provider, dict):
        data["provider"] = default_provider_config()["provider"]
    return data


def ensure_provider_config(project_root: Path) -> Path:
    path = provider_config_path(project_root)
    if not path.exists():
        write_json_atomic(path, default_provider_config())
    return path


def save_provider_config(
    project_root: Path,
    *,
    preset: str,
    base_url: str = "",
    model: str = "",
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    if preset not in PROVIDER_PRESETS:
        raise ValueError(f"Unsupported provider preset: {preset}")
    preset_data = dict(PROVIDER_PRESETS[preset])
    provider = {
        "preset": preset,
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": base_url or preset_data.get("base_url", ""),
        "model": model or preset_data.get("model", ""),
        "timeout": float(timeout if timeout is not None else preset_data.get("timeout", 60.0)),
        "max_tokens": int(max_tokens if max_tokens is not None else preset_data.get("max_tokens", 4096)),
    }
    payload = {
        "schema_version": PROVIDER_CONFIG_SCHEMA,
        "provider": provider,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_atomic(provider_config_path(project_root), payload)
    configure_production_routes(project_root, model=provider["model"])
    return payload


def configure_production_routes(project_root: Path, *, model: str = "") -> dict:
    router = load_project_router(project_root)
    router.setdefault("schema_version", "codex-writer/router/v1")
    router.setdefault("default_provider", "codex")
    routes = router.setdefault("routes", {})
    for agent in PRODUCTION_AGENT_NAMES:
        routes[agent] = {"provider": OPENAI_COMPATIBLE, "model": model or "default"}
    write_json_atomic(agent_router_path(project_root), router)
    return router


def provider_presets_public() -> dict:
    return {
        name: {
            "provider": data["provider"],
            "protocol": data["protocol"],
            "base_url": data["base_url"],
            "model": data["model"],
            "timeout": data["timeout"],
            "max_tokens": data["max_tokens"],
            "api_key_env": OPENAI_COMPATIBLE_API_KEY_ENV,
        }
        for name, data in PROVIDER_PRESETS.items()
    }


def resolve_openai_compatible_options(
    project_root: Path,
    *,
    route_model: str = "",
    cli_overrides: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or load_settings()
    cli_overrides = cli_overrides or {}
    config = load_provider_config(project_root)
    project_provider = config.get("provider") or {}
    env_timeout = os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "")
    env_max_tokens = os.environ.get("CODEX_WRITER_OPENAI_COMPATIBLE_MAX_TOKENS", "")
    preset_name = _first_non_empty(
        cli_overrides.get("preset"),
        os.environ.get("CODEX_WRITER_PROVIDER_PRESET", ""),
        project_provider.get("preset", ""),
        "custom",
    )
    preset = PROVIDER_PRESETS.get(preset_name, PROVIDER_PRESETS["custom"])
    model_from_route = route_model if route_model and route_model != "default" else ""
    resolved = {
        "preset": preset_name,
        "provider": OPENAI_COMPATIBLE,
        "protocol": "openai-compatible",
        "base_url": _first_non_empty(
            cli_overrides.get("base_url"),
            settings.openai_compatible_base_url,
            project_provider.get("base_url", ""),
            preset.get("base_url", ""),
        ),
        "api_key": settings.openai_compatible_api_key,
        "api_key_env": OPENAI_COMPATIBLE_API_KEY_ENV,
        "model": _first_non_empty(
            cli_overrides.get("model"),
            settings.openai_compatible_model,
            project_provider.get("model", ""),
            model_from_route,
            preset.get("model", ""),
        ),
        "timeout": _first_number(
            cli_overrides.get("timeout"),
            env_timeout,
            project_provider.get("timeout"),
            preset.get("timeout"),
            default=60.0,
            as_int=False,
        ),
        "max_tokens": _first_number(
            cli_overrides.get("max_tokens"),
            env_max_tokens,
            project_provider.get("max_tokens"),
            preset.get("max_tokens"),
            default=4096,
            as_int=True,
        ),
        "config_path": str(provider_config_path(project_root)),
        "configured": False,
        "api_key_present": bool(settings.openai_compatible_api_key),
    }
    resolved["configured"] = bool(resolved["base_url"] and resolved["api_key"] and resolved["model"])
    return resolved


def public_runtime_status(project_root: Path, *, route_model: str = "") -> dict:
    resolved = resolve_openai_compatible_options(project_root, route_model=route_model)
    return {
        "preset": resolved["preset"],
        "provider": resolved["provider"],
        "protocol": resolved["protocol"],
        "base_url": resolved["base_url"],
        "model": resolved["model"],
        "timeout": resolved["timeout"],
        "max_tokens": resolved["max_tokens"],
        "api_key_env": resolved["api_key_env"],
        "api_key_present": resolved["api_key_present"],
        "configured": resolved["configured"],
        "config_path": resolved["config_path"],
    }


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_number(*values: Any, default: int | float, as_int: bool) -> int | float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value) if as_int else float(value)
        except (TypeError, ValueError):
            continue
    return int(default) if as_int else float(default)
