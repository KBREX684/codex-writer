from datetime import datetime, timezone
from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import anti_ai_feedback_path

# After this many chapters without re-detection, an active item is archived.
_ARCHIVE_AFTER_CHAPTERS = 15
# Maximum number of active items kept in the store.
_MAX_ACTIVE = 50


def append_anti_ai_feedback(project_root: Path, issues: list, current_chapter: int = 0) -> list:
    """Append newly detected AI-flavor issues and archive stale ones.

    Items that have not been re-detected for *_ARCHIVE_AFTER_CHAPTERS* chapters
    are automatically moved to ``status="archived"`` so they no longer pollute
    future context packs.

    Args:
        project_root: project root path.
        issues: review issues from the current chapter.
        current_chapter: the chapter number being reviewed (used for staleness
            calculation).  Defaults to 0 (no staleness check).
    """
    fb_path = anti_ai_feedback_path(project_root)
    if fb_path.exists():
        feedback = read_json(fb_path)
        if not isinstance(feedback, list):
            feedback = []
    else:
        feedback = []

    existing_evidences = {item.get("evidence", "") for item in feedback if isinstance(item, dict)}

    count = len(feedback)
    for issue in issues:
        if issue.get("category") == "ai_flavor":
            evidence = issue.get("evidence", "")
            if evidence and evidence not in existing_evidences:
                count += 1
                feedback.append({
                    "id": f"anti-ai-{count:04d}",
                    "source_chapter": issue.get("chapter", current_chapter),
                    "last_seen_chapter": issue.get("chapter", current_chapter),
                    "text": issue.get("description", ""),
                    "evidence": evidence,
                    "fix_hint": issue.get("fix_hint", ""),
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                existing_evidences.add(evidence)
            elif evidence in existing_evidences:
                # Refresh last_seen_chapter for recurring patterns
                for item in feedback:
                    if item.get("evidence") == evidence and item.get("status") == "active":
                        item["last_seen_chapter"] = max(
                            item.get("last_seen_chapter", 0),
                            issue.get("chapter", current_chapter),
                        )
                        break

    # Archive stale items
    if current_chapter > 0:
        for item in feedback:
            if item.get("status") == "active":
                last_seen = item.get("last_seen_chapter") or item.get("source_chapter", 0)
                if last_seen and (current_chapter - last_seen) > _ARCHIVE_AFTER_CHAPTERS:
                    item["status"] = "archived"
                    item["archived_at"] = datetime.now(timezone.utc).isoformat()

    # Enforce maximum active items (keep most recent by last_seen_chapter)
    active_items = [i for i in feedback if i.get("status") == "active"]
    if len(active_items) > _MAX_ACTIVE:
        active_items.sort(key=lambda x: x.get("last_seen_chapter") or x.get("source_chapter", 0))
        to_archive_ids = {i.get("id") for i in active_items[: len(active_items) - _MAX_ACTIVE] if i.get("id")}
        for item in feedback:
            if item.get("id") in to_archive_ids:
                item["status"] = "archived"
                item.setdefault("archived_at", datetime.now(timezone.utc).isoformat())

    write_json_atomic(fb_path, feedback)
    return feedback
