import json
from pathlib import Path

from codex_writer.core.io import write_json_atomic, read_json
from codex_writer.core.paths import anti_ai_feedback_path


def append_anti_ai_feedback(project_root: Path, issues: list) -> list:
    fb_path = anti_ai_feedback_path(project_root)
    if fb_path.exists():
        feedback = read_json(fb_path)
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
                    "source_chapter": issue.get("chapter", 0),
                    "text": issue.get("description", ""),
                    "evidence": evidence,
                    "fix_hint": issue.get("fix_hint", ""),
                    "status": "active"
                })
                existing_evidences.add(evidence)

    write_json_atomic(fb_path, feedback)
    return feedback
