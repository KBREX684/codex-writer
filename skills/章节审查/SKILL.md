---
name: 章节审查
description: Review an existing chapter draft for issues.
---

# 章节审查

Use `codex-writer review --project-root <PROJECT_ROOT> --chapter <N>` to review a chapter.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
