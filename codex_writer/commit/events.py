from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import events_path
from codex_writer.storage.db import insert_event


def write_chapter_events(project_root: Path, chapter: int, events: list) -> Path:
    path = events_path(project_root, chapter)
    write_json_atomic(path, events)
    return path


def mirror_events_to_db(project_root: Path, chapter: int, events: list) -> None:
    for event in events:
        insert_event(project_root, {
            "event_id": event.get("event_id", ""),
            "chapter": chapter,
            "event_type": event.get("event_type", ""),
            "subject": event.get("subject", ""),
            "payload": event.get("payload", {}),
            "created_at": event.get("created_at", "")
        })


def read_chapter_events(project_root: Path, chapter: int) -> list:
    path = events_path(project_root, chapter)
    if not path.exists():
        return []
    return read_json(path)
