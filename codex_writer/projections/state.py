from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import state_path, chapter_md_path, chapter_brief_path


def chapter_text_word_count(project_root: Path, chapter: int, fallback_text: str = "") -> int:
    title = ""
    brief_path = chapter_brief_path(project_root, chapter)
    if brief_path.exists():
        brief = read_json(brief_path)
        title = brief.get("title", "")

    md_path = chapter_md_path(project_root, chapter, title)
    if md_path.exists():
        return len(md_path.read_text(encoding="utf-8"))
    return len(fallback_text)


def update_state_from_commit(project_root: Path, commit: dict) -> None:
    chapter = commit["meta"]["chapter"]
    status = commit["meta"]["status"]

    if state_path(project_root).exists():
        state = read_json(state_path(project_root))
    else:
        state = {
            "meta": {"schema_version": "codex-writer/state/v1"},
            "total_word_count": 0,
            "current_chapter": 0,
            "current_volume": 1,
            "chapters": {},
            "story_status": "writing"
        }

    title = ""
    brief_path = chapter_brief_path(project_root, chapter)
    if brief_path.exists():
        brief = read_json(brief_path)
        title = brief.get("title", "")

    word_count = chapter_text_word_count(project_root, chapter, commit.get("summary_text", ""))

    state["chapters"][str(chapter)] = {
        "chapter": chapter,
        "title": title,
        "status": status,
        "word_count": word_count,
        "commit_path": f".codex-writer/commits/第{chapter:04d}章提交.json"
    }

    if status == "accepted":
        state["current_chapter"] = max(state.get("current_chapter", 0), chapter)
        total = sum(ch.get("word_count", 0) for ch in state["chapters"].values() if ch.get("status") == "accepted")
        state["total_word_count"] = total

    write_json_atomic(state_path(project_root), state)
