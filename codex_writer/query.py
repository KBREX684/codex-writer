import json
from pathlib import Path

from codex_writer.core.io import read_json
from codex_writer.core.paths import state_path, memory_path


def query_entity(project_root: Path, name: str) -> dict:
    state = state_path(project_root)
    result = {"name": name, "found": False, "data": {}, "state_deltas": []}
    if state.exists():
        s = read_json(state)
        for ch_key, ch_val in s.get("chapters", {}).items():
            if name in str(ch_val):
                result["found"] = True
                result["data"][ch_key] = ch_val
    mem = memory_path(project_root)
    if mem.exists():
        m = read_json(mem)
        for fact in m.get("long_term_facts", []):
            if name in str(fact):
                result["state_deltas"].append(fact)
                result["found"] = True
        for rule in m.get("world_rules", []):
            if name in str(rule):
                result["state_deltas"].append(rule)
                result["found"] = True
    return result


def query_state_deltas(project_root: Path) -> list:
    mem = memory_path(project_root)
    if not mem.exists():
        return []
    m = read_json(mem)
    return m.get("long_term_facts", [])


def query_loops(project_root: Path) -> list:
    mem = memory_path(project_root)
    if not mem.exists():
        return []
    m = read_json(mem)
    return [loop for loop in m.get("open_loops", []) if loop.get("status") == "open"]
