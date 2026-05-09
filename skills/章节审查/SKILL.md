---
name: 章节审查
description: Review an existing chapter draft for issues.
---

# 章节审查

## 基本审查

```bash
codex-writer review --project-root <ROOT> --chapter <N>
```

## 审查维度 (v0.2)

| 维度 | 检查内容 |
|------|----------|
| 空文检测 | 正文是否为空 |
| 任务书检查 | 章节任务书是否存在 |
| AI味检测 | 模板句式、解释腔、总结句 |
| 爽点密度 | 是否有兑现、反转、打脸、震惊 |
| 节奏分析 | 段落长度分布、对话占比、场景切换 |

审查结果写入 `.codex-writer/reviews/第NNNN章审查结果.json`。

Rules:
- Do not edit `.codex-writer/state.json`, `index.sqlite`, or `commits/` directly.
- Do not bypass `review`, `extract`, or `commit`.
- If the CLI returns non-zero, report the JSON error and stop.
