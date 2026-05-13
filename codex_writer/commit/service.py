from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import (
    commit_path, review_result_path, extraction_result_path,
    chapter_brief_path, story_contract_path
)
from codex_writer.core.errors import (
    ReviewResultMissing, ExtractionResultMissing, SchemaValidationFailed
)
from codex_writer.storage.backup import create_backup_manifest


DONE_PROJECTION_STATUS = {
    "state": "done",
    "summary": "done",
    "memory": "done",
    "index": "done"
}


def commit_chapter(project_root: Path, chapter: int, no_backup: bool = False) -> dict:
    review_path = review_result_path(project_root, chapter)
    if not review_path.exists():
        raise ReviewResultMissing("审查结果缺失")

    extract_path = extraction_result_path(project_root, chapter)
    if not extract_path.exists():
        raise ExtractionResultMissing("事实抽取结果缺失")

    review = read_json(review_path)
    extraction = read_json(extract_path)

    if not isinstance(extraction.get("accepted_events"), list):
        raise SchemaValidationFailed("事实抽取 JSON 缺少 accepted_events")

    blocking_count = review.get("blocking_count", 0)
    missed_nodes = extraction.get("missed_nodes", [])
    pending_disambiguation = extraction.get("pending_disambiguation", [])

    if blocking_count > 0 or missed_nodes or pending_disambiguation:
        status = "rejected"
    else:
        status = "accepted"

    commit_data = {
        "meta": {
            "schema_version": "codex-writer/chapter-commit/v1",
            "chapter": chapter,
            "status": status
        },
        "refs": {
            "story_contract": ".codex-writer/story/故事合同.json",
            "chapter_brief": f".codex-writer/story/chapters/第{chapter:04d}章任务书.json",
            "review_result": f".codex-writer/reviews/第{chapter:04d}章审查结果.json",
            "extraction_result": ".codex-writer/tmp/extraction_result.json"
        },
        "checks": {
            "blocking_count": blocking_count,
            "missed_nodes": missed_nodes,
            "pending_disambiguation": pending_disambiguation
        },
        "accepted_events": extraction.get("accepted_events", []),
        "state_deltas": extraction.get("state_deltas", []),
        "entity_deltas": extraction.get("entity_deltas", []),
        "summary_text": extraction.get("summary_text", ""),
        "projection_status": {
            "state": "pending",
            "summary": "pending",
            "memory": "pending",
            "index": "pending"
        }
    }

    if not no_backup:
        # Incremental backup: only copies files that changed since the last
        # snapshot, keeping disk usage O(1) per chapter instead of O(N²).
        create_backup_manifest(project_root, reason=f"第{chapter}章提交前", incremental=True)

    cp = commit_path(project_root, chapter)
    write_json_atomic(cp, commit_data)

    return commit_data


def mark_projection_done(project_root: Path, chapter: int, commit: dict) -> dict:
    commit["projection_status"] = dict(DONE_PROJECTION_STATUS)
    write_json_atomic(commit_path(project_root, chapter), commit)
    return commit
