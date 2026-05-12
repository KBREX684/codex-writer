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
- Before Chapter 1 planning, confirm the foundation is already approved: story contract, worldbuilding, character cards, full-book outline, volume outline, and the relevant volume contract. If these are blank or missing, stop and help the author build them before running `codex-writer plan`.
- Confirm provider/API readiness with `codex-writer preflight --project-root <PROJECT_ROOT> --chapter <N>` before formal planning; treat this as technical readiness only, not a substitute for creative foundation planning.
- Do not manually duplicate planning logic in the skill; call the CLI and read its JSON output.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
