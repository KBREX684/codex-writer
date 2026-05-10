# Codex Writer

面向中文长篇网文作者的本地写作插件与 CLI 运行时系统。

## 快速开始

```bash
cd codex-writer
pip install -e .
codex-writer init --project-root "./我的小说" --title "我的小说" --genre "修仙"
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局"
codex-writer write --project-root "./我的小说" --chapter 1
```

## 核心命令

| 命令 | 说明 |
|------|------|
| `init` | 初始化新书项目 |
| `plan` | 生成章节任务书 |
| `write` | 执行完整写章流程（plan → draft → review → polish → extract → commit → projections）|
| `review` | 审查指定章节 |
| `extract` | 抽取章节事实 |
| `commit` | 生成并应用章节提交 |
| `query` | 查询人物、伏笔、设定 |
| `status` | 查看当前进度 |
| `events` | 查询章节事件与健康状态 |
| `preflight` | 运行时健康检查 |
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
- [后 MVP 规划](docs/codex-writer-post-mvp-backlog-v0.1.md)

## 许可

MIT
