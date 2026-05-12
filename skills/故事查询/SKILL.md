---
name: 故事查询
description: Query Codex Writer project state, characters, events, memory, references, and dashboard overview.
---

# 故事查询

Use read-only CLI commands for observation:

```bash
codex-writer dashboard --project-root <ROOT>
codex-writer bible --project-root <ROOT> status
codex-writer bible --project-root <ROOT> review
codex-writer status --project-root <ROOT> --focus all
codex-writer events --project-root <ROOT> --chapter <N>
codex-writer events --project-root <ROOT> --health
codex-writer query entity --project-root <ROOT> --name <NAME>
codex-writer query loops --project-root <ROOT>
codex-writer references search --project-root <ROOT> --query "<QUERY>"
codex-writer memory stats --project-root <ROOT>
codex-writer reading-power status --project-root <ROOT>
codex-writer preflight --project-root <ROOT> --chapter <N>
```

Workspace helpers:

```bash
codex-writer where
codex-writer resume
```

Rules:
- Treat dashboard/status/query output as read-only observation.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
