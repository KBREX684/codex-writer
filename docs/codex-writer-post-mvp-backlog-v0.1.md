# Codex Writer 后 MVP 规划 v0.1

参照对象：`lingfengQAQ/webnovel-writer`
状态：MVP 验收后重规划
日期：2026-05-09

---

## 0. 重规划原则

上一版补强清单有一个问题：它把很多“未来可能有用”的方向提前放进了路线图。现在收束。

后 MVP 阶段，`webnovel-writer` 仍然是我们的主要老师。我们先学习它已经跑出来的能力结构，不急着发散到 SaaS、商业化、多端 UI 或平台导出。

本规划只服务一个目标：

> 让 Codex Writer 从“可运行的 MVP”变成“能支撑单作者连续写 10-30 章的本地长篇网文系统”。

注意：`webnovel-writer` 使用 GPL v3。Codex Writer 当前是 MIT。后续只能学习其架构思想、命令形态、数据边界和能力优先级，不能直接复制上游代码、文档或模板内容。

---

## 1. 从 webnovel-writer 确认到的事实

截至 2026-05-09，上游仓库呈现出几个明确特征：

1. 它不是单纯 prompt 集，而是 Claude Code 插件 + Skills + Agents + Python 脚本 + references + templates + dashboard 的组合。
2. README 中明确主链已经切到 Story System：写前读取 `.story-system/MASTER_SETTING.json`、卷、章、审查合同；写后通过 accepted `CHAPTER_COMMIT` 驱动 `.webnovel/state.json`、`index.db`、`summaries/`、`memory_scratchpad.json`。
3. 它的命令入口包括 `/webnovel-init`、`/webnovel-plan`、`/webnovel-write`、`/webnovel-review`、`/webnovel-query`、`/webnovel-learn`、`/webnovel-dashboard`。
4. 它的 Agent 分工以 Context Agent、Data Agent、Reviewer 为核心，仓库里还包含 deconstruction-agent。
5. 它把 RAG 作为必做配置：默认 Embedding 使用 Qwen/Qwen3-Embedding-8B，Reranker 使用 jina-reranker-v3；未配置时可以降级到 BM25。
6. 它把 references 分成 md 与 CSV：md 负责流程规范和硬约束，CSV 负责可检索的写作知识条目。
7. 它内置题材模板与精调题材目录，包括修仙、都市、言情、规则怪谈、知乎短篇等。
8. 它引入追读力系统，围绕 Hook、Cool-point、微兑现、债务追踪进行章节级管理。
9. 它有只读 dashboard，但 dashboard 是观察面，不是主写入链路。
10. 它有 preflight、status、memory、rag、index、repair/ops 类命令，用于长期项目运维。

这些事实决定了我们的后续路线：先补“长篇写作主链的工程能力”，再考虑界面和生态。

---

## 2. 我们应该学什么，不学什么

### 应该学

| webnovel-writer 能力 | Codex Writer 学习方式 |
|---|---|
| Story System 真源划分 | 不照搬目录名，但明确写前真源、写后真源、投影读模型 |
| Skills 调 CLI | 保持 Skill 只做入口，不在 Skill 文本里实现业务逻辑 |
| Context Agent | 先做写前上下文包和章节任务书增强 |
| Data Agent | 先做事实抽取、事件、状态变化、实体变化归一化 |
| Reviewer 六维审查 | 先实现最小六维审查报告，不急着复杂打分 |
| RAG auto fallback | 先 BM25，本地稳定后再接向量和 rerank |
| references 知识库 | 先建小而准的 references，不追求 37 个题材 |
| memory_scratchpad | 先做长期记忆 scratchpad，再做压缩和冲突管理 |
| preflight/runtime health | 作为 v0.2 必做，长期项目必须能自检 |
| 只读 dashboard | 放到主链稳定后，不能先做 UI |

### 暂不学

- 不学 Claude Marketplace 发布流程，Codex 插件机制还需要单独验证。
- 不学大型 dashboard，先不做前端。
- 不学上游 37 个题材模板，先做 3-5 个高频题材的最小闭环。
- 不学复杂向量库全量能力，先保证 BM25 和本地 references 检索可用。
- 不复制上游 GPL 代码、文档、CSV、题材模板。

---

## 3. Codex Writer 当前差距

MVP 已有：

- `.codex-plugin/plugin.json`
- 中文 Skill 入口
- `codex-writer` CLI
- `init / plan / write / review / extract / commit / query / status / events / repair`
- 章节提交、投影、SQLite read model、agent_runs、基础隐私阻断

与 `webnovel-writer` 对照后，主要缺口不是“功能数量”，而是以下几条主链还薄：

1. 缺少完整文档中心：没有 README、命令详解、RAG 配置、运维说明、题材说明。
2. 缺少统一 runtime health：`doctor` 有基础检查，但没有暴露“主链是否完整、哪些源是 fallback、当前章 runtime 是否 ready”。
3. 缺少 references 知识库：审查、规划、写作没有稳定的本地知识来源。
4. 缺少 RAG / BM25 检索：目前上下文主要来自固定文件，不会检索历史章节和 references。
5. Context Agent 还是概念位：章节任务书没有自动融合长期记忆、历史摘要、伏笔、题材约束。
6. Data Agent 已具备基础抽取（P2 增强后：covered_nodes/missed_nodes、entity_deltas、scenes、dominant_thread），但缺少 entities_appeared 语义区分和 accepted_events 从文本自动生成。
7. Reviewer 维度不足（P0 修复后已正确检测所有 AI 味模式并追踪 chapter）：目前维度为"空文+AI味"，还没有爽点、节奏审查。
8. 长期记忆没有 scratchpad 分层：`memory.json` 能存事件，但还不是 working / episodic / semantic 结构。
9. 没有 learn 命令：用户写作经验无法沉淀为项目记忆。
10. 运维命令还不成体系：repair 能用，但缺少 preflight、ops 文档、长期项目恢复策略。

---

## 4. 后 MVP 路线

### v0.2：对齐老师的基础设施

目标：把 Codex Writer 从“能跑”变成“能被作者理解、能被工程师维护”。

必须完成：

- 文档中心
- 命令详解
- Windows / UTF-8 说明
- preflight / runtime health
- Skill 与 CLI 边界规范
- 当前 `.codex-writer/` 下的真源划分说明

暂不做：

- RAG 向量检索
- dashboard
- 大规模题材库
- 平台导出

### v0.3：检索增强与数据闭环 ✅ 已完成

目标：BM25 已验证，补齐 RAG 双通道 + Data Agent 抽取闭环 + 运维补强。

已完成：
- CW-W006 RAG 配置 + 4 模式（bm25/vector/hybrid/degraded）+ BM25 fallback
- CW-W008 Data Agent 增强（entities_appeared + accepted_events 自动生成 + SQLite entities/reviews 表写入）
- CW-W017 plan 命令增强（自动搜索 references 填充 style_guidance/context_summary）
- CW-W018 运维补强（backup list/verify + status --focus memory|rag）

目标：学习 `webnovel-writer` 的 references + RAG 思路，但先做本地可控版本。

必须完成：

- `references/` 目录
- md / CSV 边界
- 本地 BM25 检索
- `context` 命令增强
- 章节任务书自动吸收 references、上一章摘要、未关闭伏笔、人物状态

暂不做：

- 复杂 graph_hybrid
- 多向量库
- 远程 embedding 强依赖

### v0.4：长期记忆与审查闭环 ✅ 已完成

目标：让系统从章节生成器变成长篇写作助手。

已完成：
- CW-W010 memory scratchpad v2（episodic/semantic 双层 + bootstrap + stats/query + commit 驱动 + context 消费）
- CW-W012 追读力最小模型（debt 创建/兑现/过期 + hook 检测 + reading-power CLI + review 集成）
- CW-W009-ext 审查三维补全→六维（设定一致性 + 人物OOC浅层 + 连续性检查）
- CW-W011 learn 命令（作者经验沉淀到 memory scratchpad）
- CW-W013-rem 运维补完（repair projections --all + repair index --from-commits）

### v0.5：只读观察面 ✅ 已完成

目标：一站式观测面板 + 文档收束。

已完成：
- CW-W014 CLI Dashboard（5面板：项目/章节/审查/记忆/追读力 + 实体）
- CW-W020 文档收束（commands.md 补全 v0.3/v0.4 命令 + 3 个 SKILL.md 更新）
- CW-W021 测试硬化（dashboard + repair --all + memory stats CLI 测试）

**版本演进终态：v0.1(40) → v0.2(46) → v0.3(59) → v0.4(69) → v0.5(78 tests)**

---

## 5. 下一阶段 Issue 拆分

### CW-W001：建立文档中心 + 真源划分

**优先级**：P0
**参照**：`webnovel-writer/docs/README.md` + Story System Phase 5

**范围**：

- 新增 `README.md`
- 新增 `docs/README.md`
- 新增 `docs/guides/commands.md`
- 新增 `docs/operations/operations.md`
- 新增 `docs/architecture/overview.md`
- 在文档中统一定义 `.codex-writer/` 逻辑边界：
  - `.codex-writer/story/`：写前真源
  - `.codex-writer/commits/`：写后真源
  - `.codex-writer/state.json`、`memory.json`、`summaries/`、`index.sqlite`：投影读模型
  - `.codex-writer/logs/`、`agents/运行记录/`：观测与审计

**验收标准**：

- 新用户能从 README 进入 quickstart。
- 命令文档覆盖现有 CLI 全部子命令。
- 文档明确 Skill 只调用 CLI，不得鼓励直接改投影文件。
- 文档明确写前真源 / 写后真源 / 投影读模型 / 观测审计四层边界。
- `preflight` 能识别主链真源是否完整。

### CW-W002：新增 preflight 与 runtime health

**优先级**：P0
**参照**：`webnovel-writer` 的 `preflight` 与 `story_runtime_health`

**范围**：

- 将现有 `doctor --strict` 逻辑从 `cli.py` 抽取到新模块 `codex_writer/runtime/health.py`
- 新增 `check_mainline_health()`、`check_projection_health()` 等可复用函数
- 扩展 CLI：`preflight --format json`
- `doctor --strict` 复用 runtime health 结果

**验收标准**：

- 能输出当前章是否 ready（`mainline_ready`）。
- 能区分缺故事合同、缺章节任务书、缺 accepted commit、投影不一致。
- 输出包含 `mainline_ready`、`warnings`、`latest_commit_status`、`projection_status`。

### CW-W003：收束 Codex Writer 真源划分 → **已合并入 CW-W001**

> CW-W003 的内容（真源划分口径、逻辑边界定义）已并入 CW-W001 文档中心。不再作为独立 Issue。

### CW-W004：建立 references 最小知识库

**优先级**：P1
**参照**：上游 `references/` 的 md / CSV 分层

**范围**：

- 新增 `references/README.md`
- 新增 `references/shared/core-constraints.md`
- 新增 `references/shared/cool-points-guide.md`
- 新增 `references/review/review-schema.md`
- 新增 `references/reading-power-taxonomy.md`
- 新增 `references/csv/README.md`
- 新增最小 CSV：`写作技法.csv`、`爽点与节奏.csv`、`人设与关系.csv`

**验收标准**：

- md 用于规则、流程、审查口径。
- CSV 用于可检索知识条目。
- CSV 有校验脚本，不允许空列、重复 id、乱码标题。
- references 内容必须原创，不从上游复制。

### CW-W005：本地 BM25 检索

**优先级**：P1
**参照**：上游 RAG 的 fallback 思路

**范围**：

- 新增 `codex_writer/references/search.py`
- 支持检索 references md / CSV
- 支持检索已完成章节摘要和正文片段
- CLI 新增：`references search <query>`

**验收标准**：

- 不需要外部 API Key 即可工作。
- 搜索结果包含 `source`、`score`、`snippet`、`path`。
- 中文分词先用轻量规则，不引入重依赖。

### CW-W006：RAG 配置与可选向量检索

**优先级**：P1，但排在 BM25 之后
**参照**：上游 `rag-and-config.md`

**范围**：

- 新增 `.env.example`
- 支持 `EMBED_BASE_URL`、`EMBED_MODEL`、`EMBED_API_KEY`
- 支持 `RERANK_BASE_URL`、`RERANK_MODEL`、`RERANK_API_KEY`
- 未配置时自动回退 BM25

**验收标准**：

- 无 API Key 时主链不失败。
- 外部调用必须脱敏日志。
- `preflight` 显示 RAG 当前模式：`bm25`、`vector`、`hybrid` 或 `degraded`。

### CW-W007：Context Agent 最小实装

**优先级**：P1
**依赖**：CW-W005（BM25 检索）
**参照**：上游 Context Agent

**范围**：

- `context` 命令输出升级为“写前任务包”。
- 输入包括故事合同、卷合同、章节任务书、近期摘要、未关闭伏笔、references 检索结果。
- 输出写入 `.codex-writer/tmp/context_pack_第NNNN章.json`。

**验收标准**：

- `write` 必须先生成 context pack。
- context pack 记录每条上下文来源。
- 缺关键上下文时阻断或降级必须可见。

### CW-W008：Data Agent 抽取增强

**优先级**：P2（不在 v0.2 范围）
**参照**：上游 Data Agent / CHAPTER_COMMIT
**注意**：P2 增强后 extractor 已具备 covered_nodes、missed_nodes、entity_deltas、scenes、dominant_thread。本 Issue 仅做增量。

**范围**（缩减后）：

- 新增 `entities_appeared` 字段（语义区分于 entity_deltas）
- `accepted_events` 从章节文本自动生成（当前为空数组）
- projection 扩展写入 SQLite `entities` 表

**验收标准**：

- commit 是唯一写后事实入口。
- rejected commit 不污染 accepted 读模型。
- 抽取 JSON 无效时 commit 阻断。

### CW-W009：Reviewer 三维审查

**优先级**：P1
**依赖**：CW-W005（BM25，用于设定一致性检索）
**参照**：上游 Reviewer 六维检查
**注意**：六维中设定一致性、人物 OOC、追读力三项需要 LLM 或完整记忆系统支撑，推迟到 v0.4。

**范围**（v0.2 只做三维）：

- 爽点密度与质量：定义爽点 pattern 库，检测 cool-point/兑现/反转
- 节奏与断档：分析段落长度分布、对话/叙述比例、场景切换频率
- AI 味检测（已有，增强模式库）
- 生成 JSON 与 Markdown 两种报告

**推迟到 v0.4**：
- 设定一致性（需 BM25 + world_rules 检索 + LLM 判断）
- 人物 OOC（需角色性格库 + LLM 判断）
- 追读力（属 CW-W012 范围）

**验收标准**：

- JSON 供机器消费，Markdown 供作者阅读。
- 阻断问题和建议问题分开。
- 审查报告不直接修改正文。

### CW-W010：长期记忆 scratchpad

**优先级**：P2
**参照**：上游 `memory_scratchpad.json`

**范围**：

- 新增 `.codex-writer/memory_scratchpad.json`
- 新增 `memory stats/query/dump/conflicts/bootstrap`
- 记忆状态支持 `active`、`outdated`、`contradicted`、`tentative`

**验收标准**：

- 写后由 commit / extraction 驱动记忆更新。
- 写前由 context pack 读取记忆。
- 冲突项不自动覆盖，必须进入人工可见状态。

### CW-W011：learn 命令

**优先级**：P2
**参照**：上游 `/webnovel-learn`

**范围**：

- CLI 新增 `learn "<内容>"`
- 输出到 `.codex-writer/project_memory.json`
- 可被 context pack 消费

**验收标准**：

- 用户经验与剧情事实分开存储。
- learn 不修改 state、index、commit。
- 支持按标签或章节查询。

### CW-W012：追读力最小模型

**优先级**：P2
**参照**：上游 Hook / Cool-point / 微兑现 / 债务追踪

**范围**：

- 定义 Hook 类型。
- 定义 Cool-point 类型。
- 定义 debt：创建、延迟、兑现、过期。
- review 输出追读力建议。

**验收标准**：

- 不把追读力做成硬性分数裁决。
- 每章最多生成少量可执行建议。
- debt 能跨章查询。

### CW-W013：运维与恢复增强

**优先级**：P2
**参照**：上游 operations / backup / status / run_tests

**范围**：

- `repair projections --all`
- `repair index --from-commits`
- `backup list`
- `backup verify`
- `status --focus all|urgency|memory|rag`

**验收标准**：

- 任意投影文件删除后，可从 commits 重建。
- 备份清单可校验。
- status 输出可被 dashboard 或未来 UI 读取。

### CW-W014：只读 Dashboard / TUI 评估

**优先级**：P3
**参照**：上游 dashboard

**范围**：

- 只做技术评估，不立即实现大型前端。
- 对比 TUI、静态 HTML、轻量 Web UI。

**验收标准**：

- 明确只读边界。
- 明确数据来源只来自 CLI / read model。
- 不成为 v0.2 / v0.3 的阻塞项。

### CW-W015：references 原创性复核与 CSV 校验

**优先级**：P1
**依赖**：CW-W004（references 创建完成后执行）

**范围**：

- 创建 CSV 校验脚本 `scripts/validate_csv.py`
- 检查每列不为空、id 不重复、标题不含乱码
- 确认所有 md 与 CSV 内容为原创撰写，未从上游 GPL 仓库复制
- 校验通过后方可合并 references 到主分支

**验收标准**：

- `python scripts/validate_csv.py` 通过且无错误。
- 校验结果记录到 `.codex-writer/logs/validate_references.jsonl`。
- 每份 md / CSV 文件顶部标注原创作者与日期。

### CW-W016：skills 更新与回归测试

**优先级**：P1
**依赖**：CW-W002、CW-W004、CW-W005、CW-W007、CW-W009（新命令就绪后更新 skill）

**范围**：

- 更新 `skills/章节写作/SKILL.md` 加入 preflight、context pack 说明
- 更新 `skills/章节审查/SKILL.md` 加入三维审查维度说明
- 更新 `skills/故事查询/SKILL.md` 加入 `references search` 说明
- 扩展 `tests/cli/test_operations_commands.py` 覆盖 preflight 命令
- 扩展 `tests/integration/test_review_pipeline.py` 覆盖三维审查
- 扩展 `tests/integration/test_story_context.py` 覆盖 context pack 增强
- 运行全量 `python -m pytest -q` 通过

**验收标准**：

- 所有 Skill 文件引用最新命令。
- 全量测试 ≥ 42 项通过。
- 新增测试覆盖 v0.2 全部新命令。

---

## 6. v0.2 范围（修订后）

v0.2 纳入（8 个 Issue）：

1. CW-W001 文档中心 + 真源划分（合并 W003）
2. CW-W002 preflight 与 runtime health（含 doctor 重构）
3. CW-W004 references 最小知识库
4. CW-W005 本地 BM25 检索
5. CW-W007 Context Agent 最小实装（依赖 W005）
6. CW-W009 Reviewer 三维审查（爽点/节奏/AI味，六维→三维）
7. CW-W015 references 原创性复核 + CSV 校验
8. CW-W016 skills 更新 + 回归测试

不纳入 v0.2：
- CW-W003（已合并）
- CW-W006 向量 RAG（推迟到 BM25 验证后）
- CW-W008 Data Agent 增强（推迟，P2 已覆盖大部）
- CW-W010~CW-W014（推迟到 v0.3~v0.5）

理由：v0.2 的核心是"让主链更可靠、更像老师"。文档、健康检查、知识库、BM25、上下文增强、三维审查——这 6 项 + 2 项支撑，构成 v0.2 的最小可靠闭环。

---

## 7. 验收方式

每个 Issue 必须满足：

- 有测试。
- `python -m pytest -q` 通过。
- 涉及 CLI 的功能必须手工烟测。
- 涉及数据落盘的功能必须验证 JSON 与 SQLite。
- 涉及外部 API 的功能必须有降级路径。
- 涉及上游参考的功能必须确认没有复制 GPL 代码或文档内容。

v0.2 整体验收场景：

1. 初始化一本新书。
2. 生成第 1 章任务书。
3. preflight 显示主链 ready。
4. references search 能返回写作知识。
5. context pack 能吸收任务书、合同、references。
6. write 生成正文。
7. review 生成三维 JSON 与 Markdown 报告（爽点/节奏/AI味）。
8. commit accepted 后 state、summary、memory、index 更新。
9. runtime health 显示最新章已 projected。

---

## 8. 当前不再讨论的方向

以下方向从后 MVP 近期规划中移除：

- SaaS 后台
- 多人协作
- 移动端
- 商业化插件市场
- 平台投稿导出
- 自训练模型
- 大型可视化世界观编辑器

这些不是没价值，而是目前会分散注意力。我们先把 `webnovel-writer` 已经证明有价值的长篇主链学扎实。

---

## 9. 参考来源

- GitHub 仓库：[lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer)
- 上游 README 中的 Story System、RAG、dashboard、版本说明
- 上游 `docs/architecture/overview.md`
- 上游 `docs/guides/commands.md`
- 上游 `docs/guides/rag-and-config.md`
- 上游 `docs/memory/long-term-memory-architecture-v2.md`
- 上游 `docs/operations/operations.md`
- 上游 `webnovel-writer/references/README.md`
