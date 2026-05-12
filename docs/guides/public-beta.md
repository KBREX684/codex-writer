# Codex Writer v1.0 公测使用说明

v1.0 是开源公测版，目标是让单个中文长篇网文项目可以连续完成至少 10 章的规划、正文生成、审查、事实抽取、提交和观测。

## 必须先配置 API

正式 `plan`、`write`、`extract` 默认会调用外部模型。未配置 provider 或 API Key 时，命令会明确失败，不会静默生成样稿。

```bash
codex-writer provider --project-root "./我的小说" configure --preset custom --base-url https://api.example.com/v1 --model writer-model

set CODEX_WRITER_ALLOW_EXTERNAL_MODELS=1
set CODEX_WRITER_OPENAI_COMPATIBLE_API_KEY=<your-api-key>

codex-writer provider --project-root "./我的小说" test
codex-writer preflight --project-root "./我的小说" --chapter 1
```

`.codex-writer/agents/模型供应商.json` 不保存密钥。不要把 API Key 写进项目文件、故事设定、Skill 文档或提交记录。

## 推荐工作流

```bash
codex-writer init --project-root "./我的小说" --title "我的小说" --genre "修仙"
codex-writer provider --project-root "./我的小说" configure --preset custom --base-url https://api.example.com/v1 --model writer-model
codex-writer provider --project-root "./我的小说" test
```

初始化后先补创作底座：

1. 补 `.codex-writer/story/故事合同.json`：卖点、基调、主冲突、读者承诺、硬规则、世界规则、主要人物、文风规则和禁区。
2. 补 `.codex-writer/story/volumes/第001卷合同.json`：卷名、卷目标、关键里程碑、登场人物和卷尾钩子。
3. 在 `设定/` 下补世界观、力量体系、势力/资源/地点、人物卡等资料。
4. 在 `大纲/` 下补全书大纲、卷纲和初始章节方向。

底座完成后再进入章节生产：

```bash
codex-writer preflight --project-root "./我的小说" --chapter 1
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局"
codex-writer write --project-root "./我的小说" --chapter 1
codex-writer dashboard --project-root "./我的小说" --format html
```

连续写作时，每章重复 `preflight -> plan -> write -> dashboard/status`。如果要离线演示或测试工程闭环，使用：

```bash
codex-writer plan --project-root "./我的小说" --chapter 1 --title "入局" --demo
codex-writer write --project-root "./我的小说" --chapter 1 --demo
```

## 公测范围

- 支持 OpenAI-compatible provider 预设：`openai`、`deepseek`、`qwen`、`custom`。
- 生产必需外部 Agent：`planning_agent`、`draft_agent`、`extract_agent`。
- 本地强制步骤：`review_agent`、commit、events、state、summary、memory、index、dashboard。
- Windows + Python 3.10 是首要支持环境。

## 暂不包含

- SaaS、多用户协作、移动端。
- 商业市场上架。
- 大型前端正文编辑器。
- 真实外部 API 的 CI 测试；自动测试使用本地 mock server。
