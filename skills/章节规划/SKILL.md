---
name: 章节规划
description: Generate or update a Codex Writer chapter brief through the production planning agent.
---

# 章节规划

Formal planning defaults to the production chain and calls the external `planning_agent`:

```bash
codex-writer plan --project-root <PROJECT_ROOT> --chapter <N> --title <TITLE>
```

For offline tests or demos only:

```bash
codex-writer plan --project-root <PROJECT_ROOT> --chapter <N> --title <TITLE> --demo
```

Use `codex-writer genres list` or `codex-writer genres show --genre <GENRE>` when the author asks what genre scaffolds exist.

Rules:
- Confirm provider/API readiness with `codex-writer preflight --project-root <PROJECT_ROOT> --chapter <N>` before formal planning.
- Do not manually duplicate planning logic in the skill; call the CLI and read its JSON output.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
