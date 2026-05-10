---
name: 写作初始化
description: Initialize a new novel project with Codex Writer.
---

# 写作初始化

Use `codex-writer init --project-root <PROJECT_ROOT> --title <TITLE> --genre <GENRE>` to create a new project.
After initialization, use `codex-writer use --project-root <PROJECT_ROOT>` to bind it as the active project.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
