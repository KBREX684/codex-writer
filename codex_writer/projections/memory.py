from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import memory_path


def update_memory_from_events(project_root: Path, chapter: int, events: list) -> None:
    if memory_path(project_root).exists():
        memory = read_json(memory_path(project_root))
    else:
        memory = {
            "meta": {"schema_version": "codex-writer/memory/v1"},
            "open_loops": [],
            "reader_promises": [],
            "world_rules": [],
            "long_term_facts": []
        }

    for event in events:
        event_type = event.get("event_type", "")
        if event_type == "open_loop_created":
            memory["open_loops"].append({
                "chapter": chapter,
                "description": event.get("payload", {}).get("description", ""),
                "status": "open",
                "event_id": event.get("event_id", "")
            })
        elif event_type == "open_loop_closed":
            loop_event_id = event.get("payload", {}).get("loop_event_id", "")
            for loop in memory.get("open_loops", []):
                if loop.get("event_id") == loop_event_id:
                    loop["status"] = "closed"
        elif event_type == "world_rule_revealed":
            memory["world_rules"].append({
                "chapter": chapter,
                "rule": event.get("payload", {}).get("description", ""),
                "event_id": event.get("event_id", "")
            })
        elif event_type == "character_state_changed":
            memory["long_term_facts"].append({
                "chapter": chapter,
                "entity": event.get("subject", ""),
                "field": event.get("payload", {}).get("field", ""),
                "new_value": event.get("payload", {}).get("new_value", ""),
                "event_id": event.get("event_id", "")
            })

    write_json_atomic(memory_path(project_root), memory)
