import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.paths import codex_writer_dir


def create_backup_manifest(project_root: Path, reason: str = "") -> dict:
    cw = codex_writer_dir(project_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = cw / "backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    files_to_backup = ["state.json", "memory.json", "project.json"]
    manifest_files = []

    for fname in files_to_backup:
        src = cw / fname
        if src.exists():
            dst = backup_dir / fname
            shutil.copy2(str(src), str(dst))
            manifest_files.append({
                "path": f".codex-writer/{fname}",
                "sha256": _sha256(dst)
            })

    for sub in ["commits", "summaries", "events"]:
        src_dir = cw / sub
        if src_dir.exists():
            dst_dir = backup_dir / sub
            dst_dir.mkdir(exist_ok=True)
            for f in src_dir.iterdir():
                if f.is_file():
                    dst = dst_dir / f.name
                    shutil.copy2(str(f), str(dst))
                    manifest_files.append({
                        "path": f".codex-writer/{sub}/{f.name}",
                        "sha256": _sha256(dst)
                    })

    src_db = project_root / ".codex-writer" / "index.sqlite"
    if src_db.exists():
        dst_db = backup_dir / "index.sqlite"
        shutil.copy2(str(src_db), str(dst_db))
        manifest_files.append({
            "path": ".codex-writer/index.sqlite",
            "sha256": _sha256(dst_db)
        })

    manifest = {
        "backup_id": timestamp,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": manifest_files
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
