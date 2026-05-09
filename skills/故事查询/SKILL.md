---
name: 故事查询
description: Query characters, settings, foreshadowing, and chapter summaries.
---

# 故事查询

Use `codex-writer query entity --name <NAME>` or `codex-writer query loops --project-root <PROJECT_ROOT>` to query story data.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
