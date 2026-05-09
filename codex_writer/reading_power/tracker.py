from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.io import read_json, write_json_atomic

MIN_TEXT_FOR_HOOKS = 50
MAX_SNIPPET_CHARS = 100
DEFAULT_DEBT_WINDOW = 10

DEBT_PATH = ".codex-writer/reading_power.json"


def _load(project_root: Path) -> dict:
    from codex_writer.core.io import read_json_store
    return read_json_store(project_root / DEBT_PATH, {
        "meta": {"schema_version": "codex-writer/reading-power/v1"},
        "debts": [], "hooks": [], "cool_points": []
    })


def _save(project_root: Path, data: dict) -> None:
    from codex_writer.core.io import write_json_store
    write_json_store(project_root / DEBT_PATH, data)


def add_debt(project_root: Path, chapter: int, description: str, debt_type: str = "hook") -> dict:
    data = _load(project_root)
    entry = {
        "id": f"debt-ch{chapter:04d}-{len(data['debts'])+1:03d}",
        "chapter": chapter,
        "type": debt_type,
        "description": description,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paid_at": None
    }
    data["debts"].append(entry)
    _save(project_root, data)
    return entry


# NOTE: This function is defined for future use and tested via unit tests
def pay_debt(project_root: Path, debt_id: str) -> bool:
    data = _load(project_root)
    for debt in data["debts"]:
        if debt["id"] == debt_id and debt["status"] == "open":
            debt["status"] = "paid"
            debt["paid_at"] = datetime.now(timezone.utc).isoformat()
            _save(project_root, data)
            return True
    return False


def expire_old_debts(project_root: Path, current_chapter: int, window: int = DEFAULT_DEBT_WINDOW) -> int:
    data = _load(project_root)
    expired = 0
    for debt in data["debts"]:
        if debt["status"] == "open" and (current_chapter - debt["chapter"]) > window:
            debt["status"] = "expired"
            expired += 1
    if expired:
        _save(project_root, data)
    return expired


def get_open_debts(project_root: Path) -> list:
    data = _load(project_root)
    return [d for d in data["debts"] if d["status"] == "open"]


def get_debt_summary(project_root: Path) -> dict:
    data = _load(project_root)
    debts = data["debts"]
    return {
        "total": len(debts),
        "open": sum(1 for d in debts if d["status"] == "open"),
        "paid": sum(1 for d in debts if d["status"] == "paid"),
        "expired": sum(1 for d in debts if d["status"] == "expired"),
        "oldest_open": min((d["chapter"] for d in debts if d["status"] == "open"), default=0)
    }


# NOTE: This function is defined for future use and tested via unit tests
def record_hook(project_root: Path, chapter: int, hook_type: str, position: int = 0) -> dict:
    data = _load(project_root)
    entry = {
        "chapter": chapter,
        "type": hook_type,
        "position": position,
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }
    data["hooks"].append(entry)
    _save(project_root, data)
    return entry


def detect_hooks_from_text(text: str, chapter: int) -> list[dict]:
    hooks = []
    if len(text) > MIN_TEXT_FOR_HOOKS:
        first_line = text.strip().split("\n")[0] if text.strip() else ""
        if any(kw in first_line for kw in ["？", "!", "\u2026"]):
            hooks.append({"type": "悬念钩子", "snippet": first_line[:60], "chapter": chapter, "position": 0})

    last_paragraphs = text.strip().split("\n\n")
    if last_paragraphs:
        last = last_paragraphs[-1][:MAX_SNIPPET_CHARS]
        suspense_keywords = ["但", "然而", "不知", "暗中", "忽然", "突然", "竟然"]
        if any(kw in last for kw in suspense_keywords):
            hooks.append({"type": "信息差钩子", "snippet": last[:60], "chapter": chapter, "position": len(text)})

    return hooks


def record_cool_point(project_root: Path, chapter: int, description: str) -> None:
    data = _load(project_root)
    data["cool_points"].append({
        "chapter": chapter,
        "description": description[:100],
        "recorded_at": datetime.now(timezone.utc).isoformat()
    })
    _save(project_root, data)
