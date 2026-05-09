import json
import sqlite3
from pathlib import Path

from codex_writer.core.paths import index_db_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter INTEGER PRIMARY KEY,
    title TEXT,
    status TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    commit_path TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    current_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    chapter INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    entity_id TEXT NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    event_id TEXT
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    from_entity TEXT NOT NULL,
    to_entity TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    event_id TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    issues_count INTEGER NOT NULL,
    blocking_count INTEGER NOT NULL,
    ai_flavor_count INTEGER NOT NULL,
    review_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    chapter INTEGER,
    agent TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    input_refs_json TEXT NOT NULL,
    output_ref TEXT,
    usage_json TEXT NOT NULL,
    error_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect_db(project_root: Path) -> sqlite3.Connection:
    db_path = index_db_path(project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("SELECT 1 FROM events LIMIT 0")
    except sqlite3.OperationalError:
        conn.executescript(SCHEMA_SQL)
    return conn


def init_schema(project_root: Path) -> None:
    with connect_db(project_root) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def insert_event(project_root: Path, event: dict) -> None:
    with connect_db(project_root) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO events (event_id, chapter, event_type, subject, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event["event_id"], event["chapter"], event["event_type"], event["subject"],
             json.dumps(event.get("payload", {})), event.get("created_at", ""))
        )
        conn.commit()


def upsert_chapter(project_root: Path, record: dict) -> None:
    with connect_db(project_root) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chapters
            (chapter, title, status, word_count, summary, commit_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["chapter"],
                record.get("title", ""),
                record["status"],
                record.get("word_count", 0),
                record.get("summary", ""),
                record.get("commit_path", ""),
                record["updated_at"],
            ),
        )
        conn.commit()


def replace_review(project_root: Path, record: dict) -> None:
    with connect_db(project_root) as conn:
        conn.execute(
            "DELETE FROM reviews WHERE chapter = ? AND review_path = ?",
            (record["chapter"], record["review_path"]),
        )
        conn.execute(
            """
            INSERT INTO reviews
            (chapter, issues_count, blocking_count, ai_flavor_count, review_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record["chapter"],
                record.get("issues_count", 0),
                record.get("blocking_count", 0),
                record.get("ai_flavor_count", 0),
                record["review_path"],
            ),
        )
        conn.commit()


def insert_agent_run(project_root: Path, record: dict) -> None:
    with connect_db(project_root) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agent_runs (task_id, run_id, chapter, agent, provider, model, status, input_refs_json, output_ref, usage_json, error_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record["task_id"], record.get("run_id", ""), record.get("chapter"),
             record["agent"], record["provider"], record["model"], record["status"],
             json.dumps(record.get("input_refs", [])), record.get("output_ref", ""),
             json.dumps(record.get("usage", {})), json.dumps(record.get("errors", [])),
             record.get("created_at", ""))
        )
        conn.commit()
