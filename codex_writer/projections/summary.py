from pathlib import Path

from codex_writer.core.io import write_markdown_atomic
from codex_writer.core.paths import summary_path


def write_chapter_summary(project_root: Path, chapter: int, commit: dict) -> None:
    title = f"第{chapter:04d}章"
    content = f"# {title}\n\n"

    # Prefer the structured summary produced by extract_agent; fall back to the
    # raw summary_text field when no structured data is present.
    extraction = commit.get("extraction") or {}
    structured = extraction.get("summary_text") or commit.get("summary_text") or ""

    if structured:
        content += structured
    else:
        # Build a minimal structured summary from whatever fields are available
        lines = []
        if commit.get("title"):
            lines.append(f"【标题】{commit['title']}")
        covered = extraction.get("covered_nodes") or []
        if covered:
            lines.append(f"【兑现节点】{'、'.join(str(n) for n in covered[:5])}")
        dominant = extraction.get("dominant_thread") or ""
        if dominant:
            lines.append(f"【主线】{dominant}")
        open_loops = extraction.get("open_loops") or []
        if open_loops:
            loops_text = "、".join(str(lp.get("description", lp))[:30] for lp in open_loops[:3])
            lines.append(f"【悬念】{loops_text}")
        content += "\n".join(lines) if lines else f"（第{chapter}章已完成）"

    path = summary_path(project_root, chapter)
    write_markdown_atomic(path, content)
