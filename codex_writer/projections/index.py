import json
from pathlib import Path
from datetime import datetime, timezone

from codex_writer.core.io import read_json
from codex_writer.core.paths import chapter_brief_path, commit_path, review_result_path
from codex_writer.projections.state import chapter_text_word_count
from codex_writer.storage.db import connect_db, insert_event, replace_review, upsert_chapter
from codex_writer.storage.migrations import migrate


def update_index_from_commit(project_root: Path, chapter: int, commit: dict) -> None:
    project_root = project_root.resolve()
    migrate(project_root)

    title = ""
    brief_path = chapter_brief_path(project_root, chapter)
    if brief_path.exists():
        title = read_json(brief_path).get("title", "")

    upsert_chapter(project_root, {
        "chapter": chapter,
        "title": title,
        "status": commit["meta"]["status"],
        "word_count": chapter_text_word_count(project_root, chapter, commit.get("summary_text", "")),
        "summary": commit.get("summary_text", ""),
        "commit_path": commit_path(project_root, chapter).relative_to(project_root).as_posix(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    for event in commit.get("accepted_events", []):
        insert_event(project_root, {
            "event_id": event.get("event_id", ""),
            "chapter": chapter,
            "event_type": event.get("event_type", ""),
            "subject": event.get("subject", ""),
            "payload": event.get("payload", {}),
            "created_at": event.get("created_at", datetime.now(timezone.utc).isoformat()),
        })

    for delta in commit.get("entity_deltas", []):
        _upsert_entity(project_root, chapter, delta)

    for delta in commit.get("state_deltas", []):
        _insert_state_change(project_root, chapter, delta)

    review_path = review_result_path(project_root, chapter)
    if review_path.exists():
        review = read_json(review_path)
        issues = review.get("issues", [])
        replace_review(project_root, {
            "chapter": chapter,
            "issues_count": len(issues),
            "blocking_count": review.get("blocking_count", 0),
            "ai_flavor_count": sum(1 for i in issues if i.get("category") == "ai_flavor"),
            "review_path": review_path.relative_to(project_root).as_posix(),
        })


def _upsert_entity(project_root: Path, chapter: int, delta: dict) -> None:
    entity_id = f"entity-{delta.get('entity', 'unknown')}"
    with connect_db(project_root) as conn:
        existing = conn.execute("SELECT id FROM entities WHERE id = ?", (entity_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE entities SET name=?, type=?, aliases_json=?, current_json=?, updated_at=? WHERE id=?",
                (delta.get("entity", ""), "character", "[]",
                 json.dumps({"last_chapter": chapter, "mentioned": delta.get("mentioned", False)}),
                 datetime.now(timezone.utc).isoformat(), entity_id)
            )
        else:
            conn.execute(
                "INSERT INTO entities (id, name, type, aliases_json, current_json, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (entity_id, delta.get("entity", ""), "character", "[]",
                 json.dumps({"last_chapter": chapter, "mentioned": delta.get("mentioned", False)}),
                 datetime.now(timezone.utc).isoformat())
            )
        conn.commit()


def _insert_state_change(project_root: Path, chapter: int, delta: dict) -> None:
    entity_id = f"entity-{delta.get('entity', delta.get('subject', 'unknown'))}"
    with connect_db(project_root) as conn:
        conn.execute(
            """
            INSERT INTO state_changes
            (chapter, entity_id, field, old_value, new_value, reason, event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chapter,
                entity_id,
                delta.get("field", ""),
                delta.get("old_value", ""),
                delta.get("new_value", ""),
                delta.get("reason", ""),
                delta.get("event_id", ""),
            ),
        )
        conn.commit()
