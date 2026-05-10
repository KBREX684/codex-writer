# Codex Writer 命令详解

项目型命令支持 `--project-root <path>`，命令统一支持 `--format json` 或保持兼容的 JSON 输出。JSON 输出格式为：

```json
{"ok": true, "command": "write", "project_root": "", "run_id": "", "data": {}, "warnings": [], "errors": []}
```

退出码：

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 未分类运行时错误 |
| 2 | 参数或 schema 校验失败 |
| 3 | 写前/审查/提交阻断 |
| 4 | 隐私策略阻断 |
| 5 | provider 调用失败 |
| 6 | 文件或数据库 IO 失败 |
| 7 | 迁移失败 |

---

## init

```bash
codex-writer init --project-root <path> --title <title> --genre <genre>
```

初始化书项目，创建完整目录结构：

- `正文/` `大纲/` `设定/` `审查报告/`
- `.codex-writer/story/`（写前真源）
- `.codex-writer/commits/`（写后真源）
- `.codex-writer/state.json` `memory.json` `summaries/` `index.sqlite`（投影读模型）
- `.codex-writer/logs/` `agents/运行记录/`（观测与审计）

---

## use / where / resume

```bash
codex-writer use --project-root <path>
codex-writer where
codex-writer resume
codex-writer resume --project-root <path>
```

工作区恢复命令。`use` 将项目绑定为当前活跃项目，状态写入 `CODEX_WRITER_HOME/workspace.json` 或用户目录下的 `.codex-writer/workspace.json`。`where` 查看当前绑定项目。`resume` 根据投影状态给出下一章编号和建议命令。

---

## doctor

```bash
codex-writer doctor --project-root <path> [--strict] [--chapter N]
codex-writer doctor --self-check
```

检查项目健康状态。`--strict` 模式检查故事合同、章节任务书、迁移状态、占位符。

---

## preflight

```bash
codex-writer preflight --project-root <path> [--chapter N]
```

运行时健康检查。输出 `mainline_ready`、`projection_status`、`warnings`。

---

## plan

```bash
codex-writer plan --project-root <path> --chapter N --title <title>
```

生成或更新章节任务书（`.codex-writer/story/chapters/第NNNN章任务书.json`）。

如果项目 `genre` 命中内置题材模板，`plan` 会自动把题材风格约束和审查重点写入章节任务书。

---

## context

```bash
codex-writer context --project-root <path> --chapter N
```

输出写前资料包，包含：故事合同、章节任务书、近期摘要、未关闭伏笔、反AI反馈。

---

## write

```bash
codex-writer write --project-root <path> --chapter N [--no-backup]
```

执行完整写章流程。状态机：planned → context_ready → drafted → reviewed → polished → extracted → committed → projected。

---

## review

```bash
codex-writer review --project-root <path> --chapter N
```

审查指定章节。输出结构化审查结果 JSON 到 `.codex-writer/reviews/`。

---

## extract

```bash
codex-writer extract --project-root <path> --chapter N
```

从正文抽取结构化事实（covered_nodes、entity_deltas、scenes、dominant_thread）。

---

## commit

```bash
codex-writer commit --project-root <path> --chapter N [--no-backup]
```

生成并应用章节提交。根据审查阻断状态判定 accepted 或 rejected。accepted 触发投影写入（state、summary、memory、index）。

---

## query

```bash
codex-writer query entity --name <NAME>
codex-writer query loops
<!-- codex-writer query state-deltas  (未实现) -->
```

---

## status / events

```bash
codex-writer status --project-root <path>
codex-writer events --project-root <path> --chapter N
codex-writer events --project-root <path> --health
```

---

## migrate / backup / restore / repair

```bash
codex-writer migrate --project-root <path>
codex-writer backup --project-root <path> --reason <text>
codex-writer restore --project-root <path> --backup-id <id>
codex-writer repair projections --project-root <path> --chapter N
codex-writer repair index --project-root <path>
codex-writer repair logs --project-root <path>
```

---

## agents / route-test / run-agent

```bash
codex-writer agents --project-root <path>
codex-writer route-test --project-root <path> --agent <name> [--input-kind <kind>]
codex-writer run-agent --project-root <path> --agent <name> [--mock-output <json>]
```

---

## references search

```bash
codex-writer references search --project-root <path> --query <text>
```

本地 BM25 检索 references 知识库（`references/` 下的 md 和 CSV）。

---

## genres

```bash
codex-writer genres list
codex-writer genres show --genre 玄幻
```

查看中文网文题材模板。v0.6 内置玄幻、都市脑洞、规则怪谈、狗血言情、古言、现实题材 6 个模板。模板只提供章节规划、审查重点和路由提示，不会绕过写作主链。

---

## memory

```bash
codex-writer memory stats --project-root <path>
codex-writer memory query --project-root <path> --tag <tag>
codex-writer memory bootstrap --project-root <path>
codex-writer memory dump --project-root <path>
codex-writer memory conflicts --project-root <path>
codex-writer memory update --project-root <path> --id <entry-id> --status archived
```

管理长期记忆 scratchpad。`stats` 查看记忆统计。`query` 按标签检索记忆条目。`bootstrap` 从旧 `memory.json` 迁移数据。`dump` 导出完整 scratchpad。`conflicts` 检测同一实体同一字段的语义事实冲突。`update` 修改单条记忆状态、内容或标签。

---

## reading-power

```bash
codex-writer reading-power status --project-root <path>
codex-writer reading-power debts --project-root <path>
```

追读力管理。`status` 查看债务概览（开放/兑现/过期）。`debts` 列出当前开放的读者期待。

---

## learn

```bash
codex-writer learn "<内容>" --project-root <path> [--tag <tag>] [--chapter <N>]
```

沉淀作者写作经验到长期记忆 scratchpad。可指定标签（如 character/world_building/plot）和关联章节。

---

## backup (增强)

```bash
codex-writer backup list --project-root <path>
codex-writer backup verify --project-root <path> --backup-id <id>
```

`list` 列出所有备份及原因。`verify` 校验指定备份的 sha256 完整性。

---

## repair (增强)

```bash
codex-writer repair projections --project-root <path> --all
codex-writer repair index --project-root <path> --from-commits
```

`repair projections --all` 遍历所有 commits 批量重建投影。`repair index --from-commits` 从提交文件重建 SQLite 索引。

---

## status (增强)

```bash
codex-writer status --project-root <path> --focus memory|rag
```

`--focus memory` 附加展示记忆数据。`--focus rag` 附加展示当前 RAG 模式。

---

## dashboard

```bash
codex-writer dashboard --project-root <path> [--format json|text|html]
codex-writer dashboard --project-root <path> --format html [--output exports/dashboard.html]
```

一站式只读观测面板。整合项目概况、章节网格、审查摘要、记忆统计、追读力仪表、事件链、开放伏笔、实体与关系投影。

- `json`：稳定机器输出，供自动化或未来前端读取。
- `text`：终端可读输出。
- `html`：生成 Codex 风格高保真本地页面。默认写入 `.codex-writer/dashboard/index.html`，可通过 `--output` 指定项目内相对路径。
