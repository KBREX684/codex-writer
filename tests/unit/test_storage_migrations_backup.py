import sqlite3

from codex_writer.storage.backup import create_backup_manifest
from codex_writer.storage.db import connect_db
from codex_writer.storage.migrations import migrate


def test_migrate_is_idempotent(tmp_path):
    migrate(tmp_path)
    migrate(tmp_path)
    db = tmp_path / ".codex-writer" / "index.sqlite"
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert len(rows) == len(set(row[0] for row in rows))


def test_connect_db_uses_wal(tmp_path):
    migrate(tmp_path)
    with connect_db(tmp_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_backup_manifest_contains_sha256(tmp_path):
    root = tmp_path
    data_dir = root / ".codex-writer"
    data_dir.mkdir()
    (data_dir / "state.json").write_text('{"chapter": 1}', encoding="utf-8")
    manifest = create_backup_manifest(root, reason="提交前")
    assert manifest["reason"] == "提交前"
    assert manifest["files"][0]["sha256"]
