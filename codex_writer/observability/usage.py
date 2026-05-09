from pathlib import Path

from codex_writer.core.io import append_jsonl
from codex_writer.core.paths import codex_writer_dir


def estimate_usage(provider: str, model: str, input_text: str, output_text: str) -> dict:
    return {
        "provider": provider,
        "model": model,
        "sent_external": provider != "codex",
        "input_chars": len(input_text),
        "output_chars": len(output_text),
        "redacted": True
    }


def append_usage(project_root: Path, usage: dict) -> None:
    cw = codex_writer_dir(project_root)
    path = cw / "logs" / "agent_runs.jsonl"
    append_jsonl(path, usage)
