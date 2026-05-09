# 运维指南

## 备份与恢复

```bash
# 创建备份
codex-writer backup --project-root <path> --reason "第5章提交前"

# 列出备份
# 备份文件位于 .codex-writer/backups/<timestamp>/

# 恢复备份
codex-writer restore --project-root <path> --backup-id 20260509-120000
```

## 健康检查

```bash
# 运行时健康检查
codex-writer preflight --project-root <path> --chapter 5

# 严格检查
codex-writer doctor --project-root <path> --strict --chapter 5

# 事件一致性
codex-writer events --project-root <path> --health
```

## 投影修复

```bash
# 重建单章投影
codex-writer repair projections --project-root <path> --chapter 5

# 重建索引
codex-writer repair index --project-root <path>

# 重建运行记录
codex-writer repair logs --project-root <path>
```

## 迁移

```bash
codex-writer migrate --project-root <path>
```

幂等操作，可安全重复执行。

## 日志

运行时日志位于 `.codex-writer/logs/`：

- `workflow.jsonl` — 状态机转移记录
- `agent_runs.jsonl` — Agent/provider 调用
- `errors.jsonl` — 错误与异常
- `projections.jsonl` — 投影写入结果
