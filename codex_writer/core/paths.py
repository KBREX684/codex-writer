from pathlib import Path

from codex_writer.core.errors import PathOutsideProject


def resolve_in_project(project_root: Path, relative_path: str) -> Path:
    root = project_root.expanduser().resolve()
    target = (root / relative_path).resolve()
    if root != target and root not in target.parents:
        raise PathOutsideProject(f"路径越界: {relative_path}")
    return target


def chapter_display_name(chapter: int) -> str:
    return f"第{chapter:04d}章"


def chapter_md_path(project_root: Path, chapter: int, title: str = "") -> Path:
    name = f"{chapter_display_name(chapter)}-{title}.md" if title else f"{chapter_display_name(chapter)}.md"
    return resolve_in_project(project_root, f"正文/{name}")


def chapter_brief_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, f".codex-writer/story/chapters/{chapter_display_name(chapter)}任务书.json")


def review_result_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, f".codex-writer/reviews/{chapter_display_name(chapter)}审查结果.json")


def extraction_result_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, ".codex-writer/tmp/extraction_result.json")


def commit_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, f".codex-writer/commits/{chapter_display_name(chapter)}提交.json")


def events_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, f".codex-writer/events/{chapter_display_name(chapter)}事件.json")


def summary_path(project_root: Path, chapter: int) -> Path:
    return resolve_in_project(project_root, f".codex-writer/summaries/{chapter_display_name(chapter)}.md")


def state_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/state.json")


def memory_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/memory.json")


def project_json_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/project.json")


def index_db_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/index.sqlite")


def story_contract_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/story/故事合同.json")


def anti_ai_feedback_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/story/反AI反馈.json")


def agent_router_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/agents/子Agent路由.json")


def agent_run_dir(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/agents/运行记录")


def lock_path(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer/runtime.lock")


def codex_writer_dir(project_root: Path) -> Path:
    return resolve_in_project(project_root, ".codex-writer")
