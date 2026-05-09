---
name: 章节写作
description: Execute the Codex Writer chapter workflow through the CLI.
---

# 章节写作

Use `codex-writer write --project-root <PROJECT_ROOT> --chapter <N>` to run the workflow.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
