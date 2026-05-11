---
name: 章节审查
description: Review an existing Codex Writer chapter draft for blocking issues.
---

# 章节审查

Run local review through the CLI:

```bash
codex-writer review --project-root <ROOT> --chapter <N>
```

Review results are written to `.codex-writer/reviews/`. The local review is mandatory in production writing; external review, if added later, may only append issues and must not remove local blocking issues.

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
