---
name: 写作初始化
description: Initialize a new Codex Writer novel project and prepare provider configuration.
---

# 写作初始化

Use the CLI as the source of truth.

```bash
codex-writer init --project-root <PROJECT_ROOT> --title <TITLE> --genre <GENRE>
codex-writer provider --project-root <PROJECT_ROOT> configure --preset <openai|deepseek|qwen|custom> --base-url <BASE_URL> --model <MODEL>
codex-writer use --project-root <PROJECT_ROOT>
```

Before formal planning or writing, remind the author that v1.0 requires:

```bash
set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>
codex-writer provider --project-root <PROJECT_ROOT> test
codex-writer preflight --project-root <PROJECT_ROOT> --chapter 1
```

Rules:
- Do not write API keys into project files.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
