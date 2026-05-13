import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.paths import codex_writer_dir

# Trigger a backup every N chapters by default (configurable via env var).
_DEFAULT_BACKUP_INTERVAL = int(os.environ.get("CODEX_WRITER_BACKUP_INTERVAL", "10"))


def _last_backup_manifest(cw: Path) -> dict:
    """Return the most recent backup manifest, or empty dict if none exists."""
    backups_dir = cw / "backups"
    if not backups_dir.exists():
        return {}
    dirs = sorted(backups_dir.iterdir(), reverse=True)
    for d in dirs:
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
    return {}


def _known_sha256s(manifest: dict) -> dict[str, str]:
    """Return {relative_path: sha256} for files in a backup manifest."""
    return {entry["path"]: entry["sha256"] for entry in manifest.get("files", [])}


def create_backup_manifest(
    project_root: Path,
    reason: str = "",
    incremental: bool = True,
) -> dict:
    """Create a backup of the project's write-after truth sources.

    When *incremental* is True (the default) files that have not changed since
    the last backup are skipped.  A full copy is always used for the very first
    backup, or when *incremental* is False.
    """
    cw = codex_writer_dir(project_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = cw / "backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    last_shas = _known_sha256s(_last_backup_manifest(cw)) if incremental else {}

    def _copy_if_changed(src: Path, rel: str) -> dict | None:
        if not src.exists():
            return None
        current_sha = _sha256(src)
        if incremental and last_shas.get(rel) == current_sha:
            return None  # unchanged – skip
        dst = backup_dir / Path(rel.replace(".codex-writer/", ""))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return {"path": rel, "sha256": current_sha}

    manifest_files = []

    for fname in ["state.json", "memory.json", "project.json"]:
        entry = _copy_if_changed(cw / fname, f".codex-writer/{fname}")
        if entry:
            manifest_files.append(entry)

    for sub in ["commits", "summaries", "events"]:
        src_dir = cw / sub
        if src_dir.exists():
            for f in src_dir.iterdir():
                if f.is_file():
                    entry = _copy_if_changed(f, f".codex-writer/{sub}/{f.name}")
                    if entry:
                        manifest_files.append(entry)

    src_db = cw / "index.sqlite"
    entry = _copy_if_changed(src_db, ".codex-writer/index.sqlite")
    if entry:
        manifest_files.append(entry)

    manifest = {
        "backup_id": timestamp,
        "reason": reason,
        "incremental": incremental,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": manifest_files,
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def should_run_backup(chapter: int, interval: int = _DEFAULT_BACKUP_INTERVAL) -> bool:
    """Return True if a backup should run for this chapter number.

    Backups are triggered on the first chapter (1) and every *interval*
    chapters thereafter (e.g. 1, 10, 20, 30 …).
    """
    return chapter == 1 or chapter % interval == 0


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
