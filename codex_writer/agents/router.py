import json
from pathlib import Path

from codex_writer.core.paths import agent_router_path


def load_default_router() -> dict:
    return {
        "schema_version": "codex-writer/router/v1",
        "default_provider": "codex",
        "routes": {
            "planning_agent": {"provider": "codex", "model": "default"},
            "context_agent": {"provider": "codex", "model": "default"},
            "draft_agent": {"provider": "codex", "model": "default"},
            "review_agent": {"provider": "codex", "model": "default"},
            "polish_agent": {"provider": "codex", "model": "default"},
            "extract_agent": {"provider": "codex", "model": "default"},
            "query_agent": {"provider": "codex", "model": "default"}
        }
    }


def load_project_router(project_root: Path) -> dict:
    path = agent_router_path(project_root)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return load_default_router()


def route_agent(router: dict, agent: str) -> dict:
    routes = router.get("routes", {})
    if agent in routes:
        return routes[agent]
    default_provider = router.get("default_provider", "codex")
    return {"provider": default_provider, "model": "default"}
