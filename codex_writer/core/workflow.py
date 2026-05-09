from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import append_jsonl


WORKFLOW_STATES = {
    "planned": ["context_ready", "blocked"],
    "context_ready": ["drafted", "blocked"],
    "drafted": ["reviewed", "failed"],
    "reviewed": ["polished", "rejected"],
    "polished": ["extracted", "failed"],
    "extracted": ["committed", "rejected"],
    "committed": ["projected", "repair_needed"],
    "projected": [],
    "rejected": [],
    "failed": [],
    "blocked": [],
    "repair_needed": ["projected"],
}


def get_workflow_log_path(project_root: Path) -> Path:
    return project_root / ".codex-writer" / "logs" / "workflow.jsonl"


def log_workflow(project_root: Path, run_id: str, chapter: int, from_state: str, to_state: str, actor: str, artifact: str = "") -> None:
    path = get_workflow_log_path(project_root)
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "chapter": chapter,
        "from": from_state,
        "to": to_state,
        "actor": actor,
        "artifact": artifact
    }
    append_jsonl(path, entry)


def is_valid_transition(from_state: str, to_state: str) -> bool:
    return to_state in WORKFLOW_STATES.get(from_state, [])
