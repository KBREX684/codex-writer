"""Lightweight schema validators for Codex Writer artifacts.

These validators deliberately avoid adding external runtime dependencies.
They provide two layers of checking:

1. **Structural check** — required keys exist and have correct types.
2. **Optional jsonschema check** — if the ``jsonschema`` package is installed,
   run it against the bundled ``.schema.json`` file for full validation.

All validators return a (possibly empty) list of human-readable error strings.
An empty list means validation passed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMAS_DIR = Path(__file__).parent


def _load_schema(name: str) -> dict:
    path = _SCHEMAS_DIR / f"{name}.schema.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _check_required(data: dict, keys: list[str], context: str = "") -> list[str]:
    prefix = f"{context}: " if context else ""
    return [f"{prefix}缺少必填字段「{k}」" for k in keys if k not in data]


def _check_type(data: dict, field: str, expected: type, context: str = "") -> list[str]:
    prefix = f"{context}: " if context else ""
    if field in data and not isinstance(data[field], expected):
        return [f"{prefix}字段「{field}」类型错误（期望 {expected.__name__}，实际 {type(data[field]).__name__}）"]
    return []


def _jsonschema_validate(data: dict, schema: dict) -> list[str]:
    """Run jsonschema if available; silently skip if not installed."""
    try:
        import jsonschema  # type: ignore[import]
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            return [str(exc.message)]
        except Exception as exc:
            return [f"jsonschema 内部错误: {exc}"]
    except ImportError:
        pass
    return []


# ── Chapter Brief ─────────────────────────────────────────────────────────────

def validate_chapter_brief(data: Any) -> list[str]:
    """Validate a chapter-brief dict.  Returns a list of error strings."""
    if not isinstance(data, dict):
        return ["chapter_brief 必须是 JSON 对象"]
    errors: list[str] = []
    errors.extend(_check_required(data, ["chapter", "title"], "chapter_brief"))
    errors.extend(_check_type(data, "chapter", int, "chapter_brief"))
    errors.extend(_check_type(data, "title", str, "chapter_brief"))
    for list_field in ("must_cover_nodes", "forbidden_zones", "key_entities",
                       "character_motivation", "style_guidance", "anti_ai_reminders"):
        errors.extend(_check_type(data, list_field, list, "chapter_brief"))
    target_words = data.get("target_words")
    if target_words is not None and not isinstance(target_words, (int, float)):
        errors.append("chapter_brief: target_words 必须是数字")
    if isinstance(target_words, (int, float)) and target_words <= 0:
        errors.append("chapter_brief: target_words 必须大于 0")
    errors.extend(_jsonschema_validate(data, _load_schema("chapter_brief")))
    return errors


# ── Story Contract ─────────────────────────────────────────────────────────────

def validate_story_contract(data: Any) -> list[str]:
    """Validate a story-contract dict.  Returns a list of error strings."""
    if not isinstance(data, dict):
        return ["story_contract 必须是 JSON 对象"]
    errors: list[str] = []
    errors.extend(_check_required(data, ["meta", "book"], "story_contract"))
    if isinstance(data.get("meta"), dict):
        sv = data["meta"].get("schema_version", "")
        if sv and not sv.startswith("codex-writer/story-contract/"):
            errors.append(f"story_contract: schema_version 「{sv}」不合法")
    if isinstance(data.get("book"), dict):
        errors.extend(_check_required(data["book"], ["title", "genre"], "story_contract.book"))
    errors.extend(_jsonschema_validate(data, _load_schema("story_contract")))
    return errors


# ── Novel Bible ────────────────────────────────────────────────────────────────

def validate_novel_bible(data: Any) -> list[str]:
    """Validate the million-word novel bible.  Returns a list of error strings."""
    if not isinstance(data, dict):
        return ["novel_bible 必须是 JSON 对象"]
    errors: list[str] = []
    errors.extend(_check_required(data, ["meta", "book", "target_scale", "sections"], "novel_bible"))

    ts = data.get("target_scale", {})
    if isinstance(ts, dict):
        tw = ts.get("target_words", 0)
        tc = ts.get("target_chapters", 0)
        vc = ts.get("volume_count", 0)
        if isinstance(tw, (int, float)) and tw < 1_000_000:
            errors.append(
                f"novel_bible: target_words={tw} 低于百万字下限 1000000"
            )
        if isinstance(tc, (int, float)) and tc < 300:
            errors.append(
                f"novel_bible: target_chapters={tc} 低于下限 300"
            )
        if isinstance(vc, (int, float)) and vc < 5:
            errors.append(
                f"novel_bible: volume_count={vc} 低于下限 5"
            )
        sections = data.get("sections", {})
        volumes = sections.get("volume_roadmap", {}).get("volumes", [])
        if isinstance(volumes, list) and isinstance(vc, int) and len(volumes) != vc:
            errors.append(
                f"novel_bible: volumes 列表长度 {len(volumes)} 与 volume_count={vc} 不符"
            )
    return errors
