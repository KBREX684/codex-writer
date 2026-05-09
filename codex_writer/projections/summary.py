from pathlib import Path

from codex_writer.core.io import write_markdown_atomic
from codex_writer.core.paths import summary_path


def write_chapter_summary(project_root: Path, chapter: int, commit: dict) -> None:
    title = f"第{chapter:04d}章"
    content = f"# {title}\n\n"
    content += commit.get("summary_text", "")
    path = summary_path(project_root, chapter)
    write_markdown_atomic(path, content)
