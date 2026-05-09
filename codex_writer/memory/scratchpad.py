import json
from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json

SUMMARY_MAX_CHARS = 500
ARCHIVE_CHAPTER_WINDOW = 10
MAX_ACTIVE_EPISODIC = 50
ARCHIVE_BATCH_SIZE = 20

SCRATCHPAD_PATH = ".codex-writer/memory_scratchpad.json"


def _load(project_root: Path) -> dict:
    from codex_writer.core.io import read_json_store
    return read_json_store(project_root / SCRATCHPAD_PATH, {
        "meta": {"schema_version": "codex-writer/memory-scratchpad/v1"},
        "episodic": [], "semantic": [], "conflicts": []
    })


def _save(project_root: Path, data: dict) -> None:
    from codex_writer.core.io import write_json_store
    write_json_store(project_root / SCRATCHPAD_PATH, data)


def bootstrap(project_root: Path) -> dict:
    from codex_writer.core.io import read_json
    memory_path = project_root / ".codex-writer" / "memory.json"
    scratchpad = {
        "meta": {"schema_version": "codex-writer/memory-scratchpad/v1"},
        "episodic": [],
        "semantic": [],
        "conflicts": []
    }
    if memory_path.exists():
        old = read_json(memory_path)
        for loop in old.get("open_loops", []):
            scratchpad["episodic"].append({
                "id": loop.get("event_id", ""),
                "chapter": loop.get("chapter", 0),
                "type": "open_loop",
                "content": loop.get("description", ""),
                "status": loop.get("status", "open"),
                "tags": ["伏笔"],
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        for fact in old.get("long_term_facts", []):
            scratchpad["semantic"].append({
                "id": fact.get("event_id", ""),
                "chapter": fact.get("chapter", 0),
                "entity": fact.get("entity", ""),
                "field": fact.get("field", ""),
                "value": fact.get("new_value", ""),
                "status": "active",
                "tags": ["entity_state"],
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    _save(project_root, scratchpad)
    return scratchpad


def update_from_commit(project_root: Path, chapter: int, commit: dict) -> None:
    scratch = _load(project_root)
    events = commit.get("accepted_events", [])
    summary = commit.get("summary_text", "")
    status = commit.get("meta", {}).get("status", "")

    for event in events:
        entry = {
            "id": event.get("event_id", ""),
            "chapter": chapter,
            "type": event.get("event_type", ""),
            "subject": event.get("subject", ""),
            "payload": event.get("payload", {}),
            "status": "active",
            "tags": [event.get("event_type", "event")],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        scratch["episodic"].append(entry)

    if summary and status == "accepted":
        scratch["episodic"].append({
            "id": f"ch{chapter:04d}-summary",
            "chapter": chapter,
            "type": "chapter_summary",
            "content": summary[:SUMMARY_MAX_CHARS],
            "status": "active",
            "tags": ["summary"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    for loop in scratch.get("episodic", []):
        if loop.get("chapter", 0) < chapter - ARCHIVE_CHAPTER_WINDOW:
            loop["status"] = "archived"

    active_episodic = [e for e in scratch.get("episodic", []) if e.get("status") == "active"]
    if len(active_episodic) > MAX_ACTIVE_EPISODIC:
        for old_item in sorted(active_episodic, key=lambda x: x.get("chapter", 0))[:ARCHIVE_BATCH_SIZE]:
            old_item["status"] = "archived"

    _save(project_root, scratch)


def add_learn_entry(project_root: Path, content: str, tag: str = "", chapter: int = 0) -> dict:
    scratch = _load(project_root)
    entry = {
        "id": f"learn-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "chapter": chapter,
        "type": "author_note",
        "content": content,
        "tag": tag,
        "status": "active",
        "tags": [tag] if tag else [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    scratch["episodic"].append(entry)
    _save(project_root, scratch)
    pm_path = project_root / ".codex-writer" / "project_memory.json"
    pm_data = []
    if pm_path.exists():
        from codex_writer.core.io import read_json
        pm_data = read_json(pm_path)
    pm_data.append(entry)
    from codex_writer.core.io import write_json_atomic
    write_json_atomic(pm_path, pm_data)
    return entry


def query_memory(project_root: Path, query_type: str = "all", tag: str = "") -> list:
    scratch = _load(project_root)
    results = []
    if query_type in ("all", "episodic"):
        results.extend(scratch.get("episodic", []))
    if query_type in ("all", "semantic"):
        results.extend(scratch.get("semantic", []))
    if tag:
        results = [r for r in results if tag in str(r.get("tags", []))]
    return results


def get_memory_stats(project_root: Path) -> dict:
    scratch = _load(project_root)
    episodic = scratch.get("episodic", [])
    semantic = scratch.get("semantic", [])
    return {
        "episodic_total": len(episodic),
        "episodic_active": sum(1 for e in episodic if e.get("status") == "active"),
        "episodic_archived": sum(1 for e in episodic if e.get("status") == "archived"),
        "episodic_outdated": sum(1 for e in episodic if e.get("status") == "outdated"),
        "episodic_contradicted": sum(1 for e in episodic if e.get("status") == "contradicted"),
        "episodic_tentative": sum(1 for e in episodic if e.get("status") == "tentative"),
        "semantic_total": len(semantic),
        "conflicts_total": len(scratch.get("conflicts", [])),
        "last_updated": scratch.get("meta", {}).get("updated_at", "")
    }


def get_active_loops(project_root: Path) -> list:
    scratch = _load(project_root)
    return [e for e in scratch.get("episodic", [])
            if e.get("type") in ("open_loop", "open_loop_created")
            and e.get("status") == "active"]
