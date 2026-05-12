---
name: 章节写作
description: Execute the Codex Writer production chapter workflow through the CLI.
---

# 章节写作

Formal writing in v1.0 defaults to production mode:

Before Chapter 1 production, confirm the creative foundation is complete and approved: story contract, first volume contract, worldbuilding/power rules, character cards, full-book outline, and volume outline. If it is missing, stop before `plan` or `write` and help the author build the foundation.

```bash
codex-writer preflight --project-root <ROOT> --chapter <N>
codex-writer plan --project-root <ROOT> --chapter <N> --title "<TITLE>"
codex-writer write --project-root <ROOT> --chapter <N>
codex-writer dashboard --project-root <ROOT> --format html
```

Offline sample mode is explicit:

```bash
codex-writer plan --project-root <ROOT> --chapter <N> --title "<TITLE>" --demo
codex-writer write --project-root <ROOT> --chapter <N> --demo
```

The production `write` chain is:

```text
planned -> context_ready -> drafted -> reviewed -> polished -> extracted -> committed -> projected
```

Production boundaries:
- `draft_agent` writes the draft through the configured external provider.
- `review_agent` is always local and can block the chapter.
- `extract_agent` must return valid extraction JSON through the configured external provider.
- commit and projections remain local; external agents never write `state.json`, `index.sqlite`, or `commits/`.

Rules:
- Do not write API keys into project files or prompts.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
