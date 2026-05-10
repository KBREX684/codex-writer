from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import chapter_brief_path, project_json_path, state_path


WORKSPACE_SCHEMA = "codex-writer/workspace/v1"


def workspace_home() -> Path:
    configured = os.environ.get("CODEX_WRITER_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex-writer").resolve()


def workspace_state_path() -> Path:
    return workspace_home() / "workspace.json"


def _empty_state() -> dict:
    return {
        "meta": {"schema_version": WORKSPACE_SCHEMA},
        "active_project_root": "",
        "recent_projects": [],
        "updated_at": "",
    }


def _load_state() -> dict:
    path = workspace_state_path()
    if not path.exists():
        return _empty_state()
    try:
        state = read_json(path)
    except Exception:
        return _empty_state()
    if not isinstance(state, dict):
        return _empty_state()
    state.setdefault("meta", {"schema_version": WORKSPACE_SCHEMA})
    state.setdefault("active_project_root", "")
    state.setdefault("recent_projects", [])
    return state


def is_project_root(project_root: Path) -> bool:
    return project_json_path(project_root).exists()


def describe_project(project_root: Path) -> dict:
    root = Path(project_root).expanduser().resolve()
    project = {}
    state = {}
    if project_json_path(root).exists():
        project = read_json(project_json_path(root))
    if state_path(root).exists():
        state = read_json(state_path(root))
    return {
        "root": str(root),
        "exists": root.exists(),
        "initialized": bool(project),
        "project": {
            "title": project.get("title", ""),
            "genre": project.get("genre", ""),
            "created_at": project.get("created_at", ""),
        },
        "state": {
            "current_volume": state.get("current_volume", 1),
            "current_chapter": state.get("current_chapter", 0),
            "total_word_count": state.get("total_word_count", 0),
            "story_status": state.get("story_status", "unknown"),
        },
    }


def bind_active_project(project_root: Path) -> dict:
    root = Path(project_root).expanduser().resolve()
    if not is_project_root(root):
        return {
            "ok": False,
            "active_project_root": str(root),
            "error": {"code": "PROJECT_NOT_INITIALIZED", "message": "目标目录不是 Codex Writer 项目"},
        }

    state = _load_state()
    recent = [item for item in state.get("recent_projects", []) if item.get("root") != str(root)]
    recent.insert(0, {
        "root": str(root),
        "title": describe_project(root)["project"].get("title", ""),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    })
    state["active_project_root"] = str(root)
    state["recent_projects"] = recent[:10]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json_atomic(workspace_state_path(), state)
    return {
        "ok": True,
        "active_project_root": str(root),
        "project": describe_project(root)["project"],
        "state_file": str(workspace_state_path()),
    }


def current_workspace() -> dict:
    state = _load_state()
    root_text = state.get("active_project_root", "")
    data = {
        "active_project_root": root_text,
        "state_file": str(workspace_state_path()),
        "exists": False,
        "initialized": False,
        "project": {},
        "state": {},
        "recent_projects": state.get("recent_projects", []),
    }
    if root_text:
        described = describe_project(Path(root_text))
        data.update(described)
        data["active_project_root"] = described["root"]
    return data


def resolve_active_project() -> Path | None:
    root_text = _load_state().get("active_project_root", "")
    if not root_text:
        return None
    root = Path(root_text).expanduser().resolve()
    if not is_project_root(root):
        return None
    return root


def resume_plan(project_root: Path | None = None) -> dict:
    root = Path(project_root).expanduser().resolve() if project_root else resolve_active_project()
    if root is None:
        return {
            "ok": False,
            "error": {"code": "ACTIVE_PROJECT_MISSING", "message": "尚未绑定活跃项目，请先运行 codex-writer use"},
        }
    described = describe_project(root)
    current = int(described.get("state", {}).get("current_chapter", 0) or 0)
    next_chapter = current + 1
    brief_exists = chapter_brief_path(root, next_chapter).exists()
    commands = []
    if not brief_exists:
        commands.append(f'codex-writer plan --project-root "{root}" --chapter {next_chapter}')
    commands.append(f'codex-writer write --project-root "{root}" --chapter {next_chapter}')
    return {
        "ok": True,
        "active_project_root": str(root),
        "project": described.get("project", {}),
        "current_chapter": current,
        "next_chapter": next_chapter,
        "chapter_brief_exists": brief_exists,
        "suggested_commands": commands,
    }
