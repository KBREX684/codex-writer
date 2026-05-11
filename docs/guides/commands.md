# Codex Writer 命令详解

所有项目命令支持 `--project-root <path>`，机器可读输出使用 `--format json`。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 未分类运行时错误 |
| 2 | 参数或 schema 校验失败 |
| 3 | 写前、审查或提交阻断 |
| 4 | 隐私策略阻断 |
| 5 | provider 调用或生产配置失败 |
| 6 | 文件或数据库 IO 失败 |
| 7 | 迁移失败 |

## 初始化

```bash
codex-writer init --project-root <path> --title <title> --genre <genre>
```

初始化项目目录、故事合同、章节任务目录、Agent 路由、provider 配置模板、日志、提交、投影读模型和备份目录。

## Provider

```bash
codex-writer provider --project-root <path> presets
codex-writer provider --project-root <path> configure --preset openai|deepseek|qwen|custom --base-url <url> --model <model>
codex-writer provider --project-root <path> status
codex-writer provider --project-root <path> test
```

`provider configure` 写入 `.codex-writer/agents/模型供应商.json`，只保存 `preset`、`base_url`、`model`、`timeout`、`max_tokens` 等非密钥字段，并把 `planning_agent`、`draft_agent`、`extract_agent` 路由到 `openai_compatible`。

API Key 只能通过环境变量提供：

```bash
set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>
```

配置优先级为：CLI 参数 > 环境变量 > 项目 provider 配置 > preset 默认值。

## Preflight

```bash
codex-writer preflight --project-root <path> [--chapter N]
codex-writer preflight --project-root <path> [--chapter N] --demo
```

默认检查生产可用性，包括项目结构、章节状态、投影一致性、生产 Agent 路由、provider 配置、隐私开关和 API Key。`--demo` 只检查本地结构。

## Plan

```bash
codex-writer plan --project-root <path> --chapter N --title <title>
codex-writer plan --project-root <path> --chapter N --title <title> --demo
```

默认调用 `planning_agent` 外部模型生成章节任务书 JSON。`--demo` 使用本地模板生成任务书，适合离线测试。

`--production` 是 v0.7 兼容别名，v1.0 默认已是生产链路。

## Write

```bash
codex-writer write --project-root <path> --chapter N [--no-backup]
codex-writer write --project-root <path> --chapter N --demo
```

默认执行生产链路：

1. 生成写前资料包。
2. 调用外部 `draft_agent` 生成正文。
3. 强制执行本地 `review_agent` 阻断审查。
4. 调用外部 `extract_agent` 抽取结构化事实。
5. 本地执行 commit、events、state、summary、memory、index 投影。

缺 provider、缺 API Key、隐私未放行、模型无效 JSON、schema 不合格、本地审查阻断时，`write` 不会生成 accepted commit。

## Review / Extract / Commit

```bash
codex-writer review --project-root <path> --chapter N
codex-writer extract --project-root <path> --chapter N
codex-writer extract --project-root <path> --chapter N --demo
codex-writer commit --project-root <path> --chapter N [--no-backup]
```

`review` 始终是本地规则审查。`extract` 默认调用外部 `extract_agent`，`--demo` 使用本地抽取器。`commit` 只消费本地审查结果和抽取结果，外部 Agent 不能绕过它直接写提交。

## Project Ops

```bash
codex-writer status --project-root <path> [--focus memory|rag|all]
codex-writer events --project-root <path> --chapter N
codex-writer events --project-root <path> --health
codex-writer migrate --project-root <path>
codex-writer backup --project-root <path> --reason <text>
codex-writer backup list --project-root <path>
codex-writer backup verify --project-root <path> --backup-id <id>
codex-writer restore --project-root <path> --backup-id <id>
codex-writer repair projections --project-root <path> --all
codex-writer repair index --project-root <path> --from-commits
codex-writer repair logs --project-root <path>
```

`migrate` 会为旧项目补齐 v1.0 provider 配置文件模板，但不会写入 API Key。

## Agents

```bash
codex-writer agents --project-root <path>
codex-writer route-test --project-root <path> --agent <name> [--input-kind <kind>]
codex-writer run-agent --project-root <path> --agent <name> [--mock-output <json>]
```

生产写作的最小路由：

```json
{
  "routes": {
    "planning_agent": {"provider": "openai_compatible", "model": "writer-model"},
    "draft_agent": {"provider": "openai_compatible", "model": "writer-model"},
    "extract_agent": {"provider": "openai_compatible", "model": "writer-model"}
  }
}
```

## Knowledge And Dashboard

```bash
codex-writer references search --project-root <path> --query <text>
codex-writer genres list
codex-writer genres show --genre 玄幻
codex-writer memory stats --project-root <path>
codex-writer memory query --project-root <path> --tag <tag>
codex-writer reading-power status --project-root <path>
codex-writer dashboard --project-root <path> --format json|text|html
```

Dashboard 是只读观测面，不承担正文编辑器职责。
