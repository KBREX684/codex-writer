import json
from pathlib import Path

from codex_writer.core.io import read_json
from codex_writer.core.paths import (
    story_contract_path,
    anti_ai_feedback_path,
    chapter_brief_path,
    state_path,
    memory_path,
    summary_path,
)


def build_context_pack(project_root: Path, chapter: int) -> dict:
    cw = project_root / ".codex-writer"
    pack = {
        "story_contract": None,
        "chapter_brief": None,
        "recent_summaries": [],
        "state_snapshot": None,
        "open_loops": [],
        "anti_ai_feedback": [],
        "recent_character_changes": {},
    }

    sc = story_contract_path(project_root)
    if sc.exists():
        pack["story_contract"] = read_json(sc)

    brief = chapter_brief_path(project_root, chapter)
    if brief.exists():
        pack["chapter_brief"] = read_json(brief)

    state = state_path(project_root)
    if state.exists():
        state_data = read_json(state)
        pack["state_snapshot"] = {
            "total_word_count": state_data.get("total_word_count", 0),
            "current_chapter": state_data.get("current_chapter", 0),
            "current_volume": state_data.get("current_volume", 1),
            "chapters": {k: v for k, v in state_data.get("chapters", {}).items()}
        }

    memory = memory_path(project_root)
    if memory.exists():
        mem = read_json(memory)
        pack["open_loops"] = [loop for loop in mem.get("open_loops", []) if loop.get("status") != "closed"]

    ai_fb = anti_ai_feedback_path(project_root)
    if ai_fb.exists():
        feedback = read_json(ai_fb)
        if isinstance(feedback, list):
            pack["anti_ai_feedback"] = [item for item in feedback if item.get("status", "active") == "active"]

    prev_chapter = chapter - 1
    if prev_chapter > 0:
        prev_summary = summary_path(project_root, prev_chapter)
        if prev_summary.exists():
            pack["recent_summaries"].append(prev_summary.read_text(encoding="utf-8"))

    return pack
