---
name: 章节规划
description: Generate or update a chapter brief for the writing pipeline.
---

# 章节规划

Use `codex-writer plan --project-root <PROJECT_ROOT> --chapter <N> --title <TITLE>` to create a chapter brief.
Use `codex-writer genres list` or `codex-writer genres show --genre <GENRE>` when the author asks what genre scaffolds exist.

Notes:
- v0.6 automatically applies a matching genre template from the project `genre`.
- Do not manually duplicate template logic in the skill; call the CLI and read its JSON output.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
