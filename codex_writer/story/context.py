import os
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic
from codex_writer.core.paths import (
    story_contract_path,
    anti_ai_feedback_path,
    chapter_brief_path,
    state_path,
    memory_path,
    summary_path,
    novel_bible_path,
)
from codex_writer.story.bible import load_novel_bible

# Maximum number of recent chapter summaries to include in the context pack.
# Reads CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL env var (default 5).
_DEFAULT_CONTEXT_CHAPTERS = 5
# Maximum number of active anti-AI feedback items sent to the model (windowed).
_MAX_ANTI_AI_ITEMS = 20


def _max_context_chapters() -> int:
    try:
        return max(1, int(os.environ.get("CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL", _DEFAULT_CONTEXT_CHAPTERS)))
    except (TypeError, ValueError):
        return _DEFAULT_CONTEXT_CHAPTERS


def build_context_pack(project_root: Path, chapter: int) -> dict:
    pack = {
        "meta": {"schema_version": "codex-writer/context-pack/v1"},
        "chapter": chapter,
        "novel_bible": None,
        "story_contract": None,
        "chapter_brief": None,
        "recent_summaries": [],
        "state_snapshot": None,
        "open_loops": [],
        "anti_ai_feedback": [],
        "reading_power": {},
        "references_hits": [],
        "recent_character_changes": {},
        "sources": []
    }

    bible = load_novel_bible(project_root)
    if bible:
        pack["novel_bible"] = bible
        pack["sources"].append(str(novel_bible_path(project_root).relative_to(project_root)).replace("\\", "/"))

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

    # Load recent chapter summaries — respect CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL.
    # Iterate from offset=1 (immediately preceding chapter) outward; the resulting
    # list is already in most-recent-first order which is the intended order for the
    # model (most relevant context first).
    context_window = _max_context_chapters()
    summaries_added = []
    for offset in range(1, context_window + 1):
        prev_ch = chapter - offset
        if prev_ch < 1:
            break
        prev_summary_path = summary_path(project_root, prev_ch)
        if prev_summary_path.exists():
            summaries_added.append({
                "chapter": prev_ch,
                "text": prev_summary_path.read_text(encoding="utf-8"),
            })
            pack["sources"].append(f".codex-writer/summaries/第{prev_ch:04d}章.md")
    pack["recent_summaries"] = summaries_added

    # Anti-AI feedback: send only the most recent _MAX_ANTI_AI_ITEMS active items
    # so that old, already-fixed patterns don't waste tokens.
    ai_fb = anti_ai_feedback_path(project_root)
    if ai_fb.exists():
        feedback = read_json(ai_fb)
        if isinstance(feedback, list):
            active = [item for item in feedback if item.get("status", "active") == "active"]
            # Sort by source_chapter descending so the most recent issues come first.
            active.sort(key=lambda x: x.get("source_chapter", 0), reverse=True)
            pack["anti_ai_feedback"] = active[:_MAX_ANTI_AI_ITEMS]
        pack["sources"].append(".codex-writer/story/反AI反馈.json")

    # Reading-power: include open debts so planning/draft agents know what to pay off.
    try:
        from codex_writer.reading_power.tracker import get_open_debts, get_debt_summary
        open_debts = get_open_debts(project_root)
        debt_summary = get_debt_summary(project_root)
        pack["reading_power"] = {
            "open_debts": open_debts,
            "summary": debt_summary,
        }
        if open_debts:
            pack["sources"].append(".codex-writer/reading_power.json")
    except (ImportError, OSError):
        pass

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
