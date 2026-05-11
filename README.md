# Codex Writer

面向中文长篇网文作者的本地写作插件与 CLI 运行时系统。

当前版本：`v0.7.0`

## 快速开始

```bash
cd codex-writer
pip install -e .
codex-writer init --project-root "./我的小说" --title "我的小说" --genre "修仙"
codex-writer use --project-root "./我的小说"
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局"
codex-writer write --project-root "./我的小说" --chapter 1
codex-writer resume
```

正式规划和正文生成需要外部模型 API。v0.7 起可以先配置 OpenAI-compatible provider，再显式进入生产模式：

```bash
set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>
set CODEX_WRITER_OPENAI_COMPATIBLE_MODEL=<writer-model>

codex-writer preflight --project-root "./我的小说" --chapter 1 --production
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局" --production
codex-writer write --project-root "./我的小说" --chapter 1 --production
```

默认 `write` 仍是本地 MVP 样稿闭环；`--production` 会要求 `planning_agent` / `draft_agent` 路由到外部 provider，否则直接阻断。

## 核心命令

| 命令 | 说明 |
|------|------|
| `init` | 初始化新书项目 |
| `use` / `where` / `resume` | 绑定、查看并恢复当前写作项目 |
| `plan` | 生成章节任务书 |
| `write` | 执行完整写章流程（plan → draft → review → polish → extract → commit → projections）|
| `review` | 审查指定章节 |
| `extract` | 抽取章节事实 |
| `commit` | 生成并应用章节提交 |
| `query` | 查询人物、伏笔、设定 |
| `status` | 查看当前进度 |
| `events` | 查询章节事件与健康状态 |
| `preflight` | 运行时健康检查 |
| `genres` | 查看中文网文题材模板 |
| `memory` | 管理长期记忆 scratchpad，支持统计、查询、导出、冲突检测和条目更新 |
| `dashboard` | 生成只读观测面板，支持 text/json/html |

生成高保真本地面板：

```bash
codex-writer dashboard --project-root "./我的小说" --format html
```

## 架构

Codex Writer 采用"合同优先 + 提交优先"的主链架构：

```
故事合同 → 章节任务书 → 正文草稿 → 章节审查 → 事实抽取 → 章节提交 → 投影读模型
```

详细架构说明见 [docs/architecture/overview.md](docs/architecture/overview.md)。

## 文档

- [命令详解](docs/guides/commands.md)
- [运维指南](docs/operations/operations.md)
- [架构概述](docs/architecture/overview.md)
- [v0.7 发布说明](docs/releases/v0.7.md)
- [v0.6 发布说明](docs/releases/v0.6.md)
- [后 MVP 规划](docs/codex-writer-post-mvp-backlog-v0.1.md)

## 许可

MIT
