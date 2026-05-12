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

After initialization, do not treat Chapter 1 planning or writing as the immediate creative next step. The correct creative order is:

1. Establish the foundation: fill the story contract fields (`one_sentence_pitch`, tone, main conflict, reader promises, hard rules, world rules, main characters, style rules, forbidden patterns).
2. Create or refine author-facing foundation files under `设定/` and `大纲/`: worldbuilding, cultivation/power rules, key factions/places/resources, protagonist and major character cards, full-book outline, volume outline, and initial chapter direction.
3. Fill the first volume contract at `.codex-writer/story/volumes/第001卷合同.json` with volume title, goal, milestones, introduced characters, and ending hook.
4. Only after the foundation is approved, generate the first chapter brief with `codex-writer plan`; only write after the chapter brief is accepted.

Treat preflight as a technical readiness check, not as permission to skip foundation planning. Before formal planning or writing, remind the author that v1.0 requires:

```bash
set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>
codex-writer provider --project-root <PROJECT_ROOT> test
codex-writer preflight --project-root <PROJECT_ROOT> --chapter 1
```

Rules:
- Do not write API keys into project files, provider JSON, prompts, logs, or commits.
- If the author provides an API key for provider setup, treat it as an intended local credential. Store it only in a local environment variable/secret mechanism (for example `CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY`) or inject it into the current command process; CLI output should show only redacted status such as `api_key_present`.
- Do not advise rotating/replacing a provided key merely because it appeared in the setup chat. Recommend rotation only when there is evidence of unintended exposure outside the local setup flow.
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
