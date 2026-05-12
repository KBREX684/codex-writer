import json
from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import read_json
from codex_writer.runtime.rag import get_search_mode
from codex_writer.core.paths import (
    codex_writer_dir, story_contract_path, chapter_brief_path,
    review_result_path, extraction_result_path, commit_path,
    state_path, events_path, summary_path, memory_path, index_db_path
)


def check_mainline_health(project_root: Path, chapter: int = None, require_foundation: bool = False) -> dict:
    cw = codex_writer_dir(project_root)
    result = {
        "mainline_ready": True,
        "time": datetime.now(timezone.utc).isoformat(),
        "chapter": chapter,
        "checks": {},
        "warnings": [],
        "latest_commit_status": None,
        "projection_status": {}
    }
    result["rag_mode"] = get_search_mode(project_root)

    if not cw.exists():
        result["mainline_ready"] = False
        result["warnings"].append({"code": "PROJECT_NOT_INITIALIZED", "message": "项目未初始化"})
        return result

    sc = story_contract_path(project_root)
    result["checks"]["story_contract"] = sc.exists()
    if not sc.exists():
        result["mainline_ready"] = False
        result["warnings"].append({"code": "STORY_CONTRACT_MISSING", "message": "故事合同缺失"})

    try:
        from codex_writer.story.foundation import check_foundation_ready

        foundation = check_foundation_ready(project_root)
        result["foundation"] = foundation
        if require_foundation and not foundation["ready"]:
            result["mainline_ready"] = False
            result["warnings"].extend(foundation["warnings"])
    except Exception as exc:
        result["foundation"] = {"ready": False, "error": str(exc)}
        if require_foundation:
            result["mainline_ready"] = False
            result["warnings"].append({
                "code": "FOUNDATION_CHECK_FAILED",
                "message": "创作底座检查失败",
            })

    project_json = cw / "project.json"
    result["checks"]["project_json"] = project_json.exists()

    if chapter is not None:
        brief = chapter_brief_path(project_root, chapter)
        result["checks"]["chapter_brief"] = brief.exists()
        if not brief.exists():
            result["warnings"].append({"code": "CHAPTER_BRIEF_MISSING", "message": f"第{chapter}章任务书缺失"})

        review = review_result_path(project_root, chapter)
        result["checks"]["review_result"] = review.exists()

        extraction = extraction_result_path(project_root, chapter)
        result["checks"]["extraction_result"] = extraction.exists()

        cp = commit_path(project_root, chapter)
        result["checks"]["commit"] = cp.exists()
        if cp.exists():
            commit_data = read_json(cp)
            result["latest_commit_status"] = commit_data.get("meta", {}).get("status")
            result["projection_status"] = commit_data.get("projection_status", {})

    state = state_path(project_root)
    result["checks"]["state"] = state.exists()

    mem = memory_path(project_root)
    result["checks"]["memory"] = mem.exists()

    db = index_db_path(project_root)
    result["checks"]["index_db"] = db.exists()

    logs_dir = cw / "logs"
    result["checks"]["logs"] = logs_dir.exists()

    events_dir = cw / "events"
    if events_dir.exists():
        result["checks"]["events_count"] = len(list(events_dir.glob("*.json")))

    return result


def check_projection_health(project_root: Path, chapter: int) -> dict:
    cw = codex_writer_dir(project_root)
    result = {"consistent": True, "issues": []}

    cp = commit_path(project_root, chapter)
    if not cp.exists():
        result["consistent"] = False
        result["issues"].append({"code": "COMMIT_MISSING", "message": f"第{chapter}章提交缺失"})
        return result

    commit_data = read_json(cp)
    status = commit_data.get("meta", {}).get("status")

    sp = state_path(project_root)
    if sp.exists():
        state_data = read_json(sp)
        ch_state = state_data.get("chapters", {}).get(str(chapter))
        if not ch_state:
            result["issues"].append({"code": "STATE_MISSING", "message": f"state.json 缺少第{chapter}章"})
        elif ch_state.get("status") != status:
            result["issues"].append({"code": "STATE_MISMATCH", "message": f"state 与 commit 状态不一致"})

    sm = summary_path(project_root, chapter)
    if status == "accepted" and not sm.exists():
        result["issues"].append({"code": "SUMMARY_MISSING", "message": f"第{chapter}章摘要缺失"})

    ep = events_path(project_root, chapter)
    result["checks"] = {"events_file": ep.exists(), "summary_file": sm.exists()}

    if result["issues"]:
        result["consistent"] = False

    return result
