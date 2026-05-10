---
name: 故事查询
description: Query characters, settings, foreshadowing, chapter summaries, references, and dashboard overview.
---

# 故事查询

## 一站式观测

```bash
codex-writer dashboard --project-root <ROOT>
```

## 工作区恢复

```bash
codex-writer where
codex-writer resume
```

## 人物查询

```bash
codex-writer query entity --name <NAME> --project-root <ROOT>
```

## 伏笔查询

```bash
codex-writer query loops --project-root <ROOT>
```

## 状态与事件

```bash
codex-writer status --project-root <ROOT> [--focus memory|rag]
codex-writer events --chapter <N> --project-root <ROOT>
codex-writer events --health --project-root <ROOT>
codex-writer preflight --project-root <ROOT> --chapter <N>
```

## 知识库检索

```bash
codex-writer references search --query "武侠爽点写法" --project-root <ROOT>
```

## 记忆与追读力

```bash
codex-writer memory stats --project-root <ROOT>
codex-writer memory query --project-root <ROOT> --tag character
codex-writer memory dump --project-root <ROOT>
codex-writer memory conflicts --project-root <ROOT>
codex-writer reading-power status --project-root <ROOT>
codex-writer reading-power debts --project-root <ROOT>
```

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
