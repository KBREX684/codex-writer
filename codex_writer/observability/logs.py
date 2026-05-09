"""Observability logging stubs.

Note: For workflow logging, use `codex_writer.core.workflow.log_workflow()` instead.
These functions are kept as reference stubs for API compatibility.
"""
from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.io import append_jsonl
from codex_writer.core.paths import codex_writer_dir


def write_workflow_log(project_root: Path, run_id: str, chapter: int,
                       from_state: str, to_state: str, actor: str, artifact: str) -> None:
    cw = codex_writer_dir(project_root)
    path = cw / "logs" / "workflow.jsonl"
    append_jsonl(path, {
        "time": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "chapter": chapter,
        "from": from_state,
        "to": to_state,
        "actor": actor,
        "artifact": artifact
    })


def write_error_log(project_root: Path, run_id: str, chapter: int,
                    code: str, message: str, recoverable: bool = True,
                    artifact: str = "") -> None:
    cw = codex_writer_dir(project_root)
    path = cw / "logs" / "errors.jsonl"
    append_jsonl(path, {
        "time": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "chapter": chapter,
        "code": code,
        "message": message,
        "recoverable": recoverable,
        "artifact": artifact
    })
