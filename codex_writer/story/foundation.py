from __future__ import annotations

from pathlib import Path
from typing import Any

from codex_writer.core.io import read_json
from codex_writer.core.paths import resolve_in_project, story_contract_path


STORY_CORE_FIELDS = ("one_sentence_pitch", "core_tone", "main_conflict")
STORY_LIST_FIELDS = ("reader_promise",)
STORY_TOP_LEVEL_LIST_FIELDS = (
    "hard_rules",
    "world_rules",
    "main_characters",
    "style_rules",
    "forbidden_patterns",
)
VOLUME_FIELDS = ("title", "goal", "ending_hook")
VOLUME_LIST_FIELDS = ("key_milestones", "characters_introduced")


def check_foundation_ready(project_root: Path, volume: int = 1) -> dict:
    """Check whether the creative foundation is substantial enough for chapter planning."""
    story = _read_json_if_exists(story_contract_path(project_root))
    volume_path = resolve_in_project(project_root, f".codex-writer/story/volumes/第{volume:03d}卷合同.json")
    volume_contract = _read_json_if_exists(volume_path)

    story_checks = _story_contract_checks(story)
    volume_checks = _volume_contract_checks(volume_contract)
    setting_files = _non_empty_files(resolve_in_project(project_root, "设定"))
    outline_files = _non_empty_files(resolve_in_project(project_root, "大纲"))

    checks = {
        "story_contract_exists": story is not None,
        "story_contract": story_checks,
        "volume_contract_exists": volume_contract is not None,
        "volume_contract": volume_checks,
        "setting_files": bool(setting_files),
        "outline_files": bool(outline_files),
    }
    missing = []
    if story is None:
        missing.append("story_contract")
    missing.extend(f"story_contract.{name}" for name, ok in story_checks.items() if not ok)
    if volume_contract is None:
        missing.append(f"volume_{volume:03d}_contract")
    missing.extend(f"volume_{volume:03d}_contract.{name}" for name, ok in volume_checks.items() if not ok)
    if not setting_files:
        missing.append("设定/*.md")
    if not outline_files:
        missing.append("大纲/*.md")

    ready = not missing
    warnings = []
    if not ready:
        warnings.append({
            "code": "FOUNDATION_INCOMPLETE",
            "message": "创作底座未完成：请先补故事合同、世界观/人物卡、全书/卷级大纲和卷合同，再进入第1章任务书。",
            "missing": missing,
        })

    return {
        "ready": ready,
        "checks": checks,
        "missing": missing,
        "setting_files": setting_files,
        "outline_files": outline_files,
        "warnings": warnings,
    }


def foundation_not_ready_error(foundation: dict) -> dict:
    return {
        "code": "FOUNDATION_NOT_READY",
        "message": "第1章正式规划前必须先完成创作底座：故事合同、世界观/人物卡、全书/卷级大纲和卷合同。",
        "blocking": True,
        "missing": foundation.get("missing", []),
    }


def _story_contract_checks(story: dict[str, Any] | None) -> dict[str, bool]:
    core = story.get("core", {}) if isinstance(story, dict) else {}
    checks = {name: _has_text(core.get(name)) for name in STORY_CORE_FIELDS}
    checks.update({name: _has_items(core.get(name)) for name in STORY_LIST_FIELDS})
    for name in STORY_TOP_LEVEL_LIST_FIELDS:
        checks[name] = _has_items(story.get(name) if isinstance(story, dict) else None)
    return checks


def _volume_contract_checks(volume: dict[str, Any] | None) -> dict[str, bool]:
    checks = {name: _has_text(volume.get(name) if isinstance(volume, dict) else None) for name in VOLUME_FIELDS}
    for name in VOLUME_LIST_FIELDS:
        checks[name] = _has_items(volume.get(name) if isinstance(volume, dict) else None)
    return checks


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _non_empty_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            files.append(str(path.relative_to(root.parent)).replace("\\", "/"))
    return files


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_items(value: Any) -> bool:
    return isinstance(value, list) and any(item for item in value if item)
