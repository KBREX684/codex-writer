from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import state_path, chapter_md_path, chapter_brief_path


def _count_chinese_chars(text: str) -> int:
    """Count Chinese characters plus Chinese punctuation (fullwidth forms).

    Excludes ASCII whitespace, Markdown structural characters (# * > ─), and
    newlines.  This matches the industry standard for 字数统计 on platforms like
    起点 and 晋江.
    """
    return sum(
        1 for ch in text
        if "\u4e00" <= ch <= "\u9fff"          # CJK unified ideographs
        or "\u3000" <= ch <= "\u303f"           # CJK symbols & punctuation
        or "\uff00" <= ch <= "\uffef"           # Fullwidth Latin / halfwidth Katakana
        # Punctuation not covered by the ranges above that appear in novels:
        # \u201c/\u201d = curly double quotes (dialogue), \u2018/\u2019 = curly single quotes,
        # \u2014 = em dash, \u2026 = ellipsis
        or ch in "\u201c\u201d\u2018\u2019\u2014\u2026"
    )


def chapter_text_word_count(project_root: Path, chapter: int, fallback_text: str = "") -> int:
    title = ""
    brief_path = chapter_brief_path(project_root, chapter)
    if brief_path.exists():
        brief = read_json(brief_path)
        title = brief.get("title", "")

    md_path = chapter_md_path(project_root, chapter, title)
    if md_path.exists():
        return _count_chinese_chars(md_path.read_text(encoding="utf-8"))
    return _count_chinese_chars(fallback_text)


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

    # Always recalculate total_word_count so that status changes such as
    # "reverted" correctly exclude the chapter from the running total.
    state["total_word_count"] = sum(
        ch.get("word_count", 0)
        for ch in state["chapters"].values()
        if ch.get("status") == "accepted"
    )

    write_json_atomic(state_path(project_root), state)
