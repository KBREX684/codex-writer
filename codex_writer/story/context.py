import json
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
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
        "meta": {"schema_version": "codex-writer/context-pack/v1"},
        "chapter": chapter,
        "story_contract": None,
        "chapter_brief": None,
        "recent_summaries": [],
        "state_snapshot": None,
        "open_loops": [],
        "anti_ai_feedback": [],
        "references_hits": [],
        "recent_character_changes": {},
        "sources": []
    }

    sc = story_contract_path(project_root)
    if sc.exists():
        pack["story_contract"] = read_json(sc)
        pack["sources"].append(".codex-writer/story/故事合同.json")

    brief = chapter_brief_path(project_root, chapter)
    if brief.exists():
        pack["chapter_brief"] = read_json(brief)
        pack["sources"].append(f".codex-writer/story/chapters/第{chapter:04d}章任务书.json")

    state = state_path(project_root)
    if state.exists():
        state_data = read_json(state)
        pack["state_snapshot"] = {
            "total_word_count": state_data.get("total_word_count", 0),
            "current_chapter": state_data.get("current_chapter", 0),
            "current_volume": state_data.get("current_volume", 1),
            "chapters": {k: v for k, v in state_data.get("chapters", {}).items()}
        }
        pack["sources"].append(".codex-writer/state.json")

    memory = memory_path(project_root)
    if memory.exists():
        mem = read_json(memory)
        pack["open_loops"] = [loop for loop in mem.get("open_loops", []) if loop.get("status") != "closed"]
        pack["sources"].append(".codex-writer/memory.json")

    ai_fb = anti_ai_feedback_path(project_root)
    if ai_fb.exists():
        feedback = read_json(ai_fb)
        if isinstance(feedback, list):
            pack["anti_ai_feedback"] = [item for item in feedback if item.get("status", "active") == "active"]
        pack["sources"].append(".codex-writer/story/反AI反馈.json")

    prev_chapter = chapter - 1
    if prev_chapter > 0:
        prev_summary = summary_path(project_root, prev_chapter)
        if prev_summary.exists():
            pack["recent_summaries"].append({"chapter": prev_chapter, "text": prev_summary.read_text(encoding="utf-8")})
            pack["sources"].append(f".codex-writer/summaries/第{prev_chapter:04d}章.md")

    try:
        from codex_writer.references.search import search_references
        search_query = ""
        if pack["chapter_brief"]:
            search_query = pack["chapter_brief"].get("title", "") + " " + pack["chapter_brief"].get("goal", "")
        if search_query.strip():
            hits = search_references(project_root, search_query, top_k=5)
            pack["references_hits"] = hits
            pack["sources"].append("references (BM25)")
    except ImportError:
        pass

    return pack


def write_context_pack(project_root: Path, chapter: int) -> Path:
    pack = build_context_pack(project_root, chapter)
    output_path = project_root / ".codex-writer" / "tmp" / f"context_pack_第{chapter:04d}章.json"
    write_json_atomic(output_path, pack)
    return output_path
