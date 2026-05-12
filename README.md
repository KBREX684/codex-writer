# Codex Writer

面向中文长篇网文作者的本地写作插件与 CLI 运行时。

当前版本：`v1.0.0`

## 快速开始

正式规划和正文生成需要配置外部模型 API。Codex Writer v1.0 使用 OpenAI-compatible `/chat/completions` 协议，项目文件只保存非密钥配置，API Key 只从环境变量读取。

```bash
cd codex-writer
pip install -e .

codex-writer init --project-root "./我的小说" --title "我的小说" --genre "修仙"
codex-writer provider --project-root "./我的小说" configure --preset custom --base-url https://api.example.com/v1 --model writer-model

set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>
set CODEX_WRITER_MAX_CONTEXT_CHAPTERS_EXTERNAL=100

codex-writer provider --project-root "./我的小说" test
codex-writer bible --project-root "./我的小说" create --target-words 1000000 --target-chapters 500 --volume-count 6 --author-input "<author premise and preferences>"
codex-writer bible --project-root "./我的小说" review
codex-writer bible --project-root "./我的小说" approve
codex-writer preflight --project-root "./我的小说" --chapter 1
```

初始化后先补创作底座，不要直接进入第 1 章：

- 填写 `.codex-writer/story/故事合同.json`：一句话卖点、基调、主冲突、读者承诺、硬规则、世界规则、主要人物、文风规则和禁区。
- 填写 `.codex-writer/story/volumes/第001卷合同.json`：卷名、卷目标、关键里程碑、登场人物和卷尾钩子。
- 在 `设定/` 下补世界观、力量体系、势力/资源/地点、人物卡等资料。
- 在 `大纲/` 下补全书大纲、卷纲和初始章节方向。

底座完成后再进入章节生产：

```bash
codex-writer preflight --project-root "./我的小说" --chapter 1
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局"
codex-writer write --project-root "./我的小说" --chapter 1
codex-writer dashboard --project-root "./我的小说" --format html
```

离线测试或演示样稿请显式使用 `--demo`：

```bash
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局" --demo
codex-writer write --project-root "./我的小说" --chapter 1 --demo
```

`--production` 作为 v0.7 兼容别名保留到 v1.1；v1.0 中默认已经是生产链路。

## 核心命令

| 命令 | 说明 |
| --- | --- |
| `init` | 初始化新书项目 |
| `provider presets/configure/status/test` | 查看、配置、检查外部模型供应商 |
| `preflight` | 检查项目结构和生产写作可用性 |
| `plan` | 默认调用 `planning_agent` 外部模型生成章节任务书；第 1 章正式规划前会阻断空白创作底座 |
| `write` | 默认执行生产链路：外部正文生成、本地审查、外部事实抽取、本地提交和投影 |
| `review` | 本地规则审查指定章节 |
| `extract` | 默认调用 `extract_agent` 外部模型抽取结构化事实 |
| `commit` | 生成并应用章节提交 |
| `status` / `events` / `query` | 查看项目状态、事件链和读模型 |
| `memory` / `reading-power` | 管理长期记忆与追读债务 |
| `dashboard` | 生成只读观测面板，支持 text/json/html |

## 生产边界

- `planning_agent`、`draft_agent`、`extract_agent` 必须路由到外部模型。
- `review_agent` 的本地阻断审查始终强制执行；外部审查只能追加问题，不能覆盖本地阻断。
- 外部 Agent 不能直接写 `state.json`、`index.sqlite`、`commits/`，也不能自行判定 accepted。
- 模型返回空输出、无效 JSON 或 schema 不合格时会阻断，不会生成 accepted commit。

## 文档

- [命令详解](docs/guides/commands.md)
- [公测使用说明](docs/guides/public-beta.md)
- [运维指南](docs/operations/operations.md)
- [架构概览](docs/architecture/overview.md)
- [v1.0 发布说明](docs/releases/v1.0.md)
- [v0.7 发布说明](docs/releases/v0.7.md)
- [v0.6 发布说明](docs/releases/v0.6.md)

## 许可

MIT
