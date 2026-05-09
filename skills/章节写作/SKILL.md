---
name: 章节写作
description: Execute the Codex Writer chapter workflow through the CLI.
---

# 章节写作

## 完整流程

1. 观测面板：`codex-writer dashboard --project-root <ROOT>`
2. 健康检查：`codex-writer preflight --project-root <ROOT> --chapter <N>`
3. 生成任务书：`codex-writer plan --project-root <ROOT> --chapter <N> --title "标题"`
4. 执行写章：`codex-writer write --project-root <ROOT> --chapter <N>`

## write 命令内部步骤

```
planned → context_ready → drafted → reviewed → extracted → committed → projected
```

系统自动执行：上下文包生成（含 BM25/RAG + 记忆 scratchpad）→ 正文起草 → 六维审查（爽点/节奏/AI味/设定/人物/连续性）→ 事实抽取 + 实体追踪 → 章节提交 → 投影更新 + 记忆 scratchpad 更新 + 追读力债务管理

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- If the CLI returns non-zero, report the JSON error and stop.
