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


def list_backups(project_root: Path) -> list[dict]:
    cw = project_root / ".codex-writer" / "backups"
    if not cw.exists():
        return []
    backups = []
    for backup_dir in sorted(cw.iterdir(), reverse=True):
        manifest = backup_dir / "manifest.json"
        if manifest.exists():
            import json
            data = json.loads(manifest.read_text(encoding="utf-8"))
            backups.append({
                "backup_id": data.get("backup_id", backup_dir.name),
                "reason": data.get("reason", ""),
                "created_at": data.get("created_at", ""),
                "file_count": len(data.get("files", []))
            })
    return backups


def verify_backup(project_root: Path, backup_id: str) -> dict:
    cw = project_root / ".codex-writer" / "backups"
    backup_dir = cw / backup_id
    result = {"backup_id": backup_id, "exists": False, "files_ok": 0, "files_missing": 0, "sha256_mismatch": 0}

    if not backup_dir.exists():
        return result

    result["exists"] = True
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        result["files_missing"] = -1
        return result

    import json
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    import hashlib

    for file_entry in manifest.get("files", []):
        fname = file_entry.get("path", "").replace(".codex-writer/", "")
        fpath = backup_dir / fname
        if not fpath.exists():
            result["files_missing"] += 1
            continue
        h = hashlib.sha256()
        with open(fpath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if h.hexdigest() == file_entry.get("sha256", ""):
            result["files_ok"] += 1
        else:
            result["sha256_mismatch"] += 1

    return result
