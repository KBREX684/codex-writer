import json
import os
from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import write_json_atomic
from codex_writer.core.paths import agent_run_dir
from codex_writer.observability.usage import estimate_usage, append_usage
from codex_writer.storage.db import insert_agent_run

# When set to a truthy value, agent run records omit the raw input/output text.
# This prevents large model outputs from accumulating in .codex-writer/agents/运行记录/.
_NO_STORE_RAW = os.environ.get("CODEX_WRITER_NO_STORE_RAW", "").strip().lower() in {
    "1", "true", "yes", "on"
}


def write_agent_run(project_root: Path, record: dict,
                    input_text: str = "", output_text: str = "") -> Path:
    run_dir = agent_run_dir(project_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    task_id = record.get("task_id", f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    filename = f"{task_id}.json"
    path = run_dir / filename
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    usage_data = estimate_usage(
        provider=record.get("provider", ""),
        model=record.get("model", ""),
        input_text=input_text,
        output_text=output_text
    )
    if not record.get("usage"):
        record["usage"] = usage_data

    if _NO_STORE_RAW:
        # Omit raw text to reduce disk usage; usage stats are preserved.
        record.pop("input_text", None)
        record.pop("output_text", None)
    else:
        if input_text:
            record.setdefault("input_text", input_text)
        if output_text:
            record.setdefault("output_text", output_text)

    write_json_atomic(path, record)
    insert_agent_run(project_root, record)
    append_usage(project_root, usage_data)
    return path


def create_agent_task(agent: str, task_id: str, provider: str, model: str,
                      input_refs: list = None, output_ref: str = "") -> dict:
    return {
        "task_id": task_id,
        "run_id": f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "agent": agent,
        "provider": provider,
        "model": model,
        "status": "running",
        "input_refs": input_refs or [],
        "output_ref": output_ref,
        "usage": {},
        "errors": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
