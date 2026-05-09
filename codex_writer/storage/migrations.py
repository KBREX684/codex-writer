import json
from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.paths import codex_writer_dir
from codex_writer.storage.db import init_schema

REGISTERED_MIGRATIONS = [
    "202605090000_initial_schema",
]


def migrate(project_root: Path) -> None:
    cw = codex_writer_dir(project_root)
    cw.mkdir(parents=True, exist_ok=True)
    applied_path = cw / "migrations" / "applied.json"
    applied_path.parent.mkdir(parents=True, exist_ok=True)

    if applied_path.exists():
        applied = json.loads(applied_path.read_text(encoding="utf-8"))
    else:
        applied = []

    for version in REGISTERED_MIGRATIONS:
        if version not in applied:
            if version == "202605090000_initial_schema":
                init_schema(project_root)
            applied.append(version)

    applied_path.write_text(json.dumps(applied, ensure_ascii=False, indent=2), encoding="utf-8")
