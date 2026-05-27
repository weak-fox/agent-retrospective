# agent-retrospective 中文说明

`agent-retrospective` 是一个显式触发的 Codex skill，也是一个本地优先的增量复盘工具。它会读取本机 agent 会话历史，把新增或变更的 session 总结进一个私有复盘知识库，用于长期反思、周报、年报和自我改进。

## 适用场景

- 你想定期复盘自己如何使用 Codex 或其他 AI coding agent。
- 你希望复盘是增量的，而不是每次重新扫描和重写全部历史。
- 你希望保留真实项目名、路径和任务背景，但不想把这些内容放进公开仓库。
- 你希望以后扩展到 Claude Code、Cursor CLI、OpenCode 等多个 agent。

## 触发方式

这个 skill 只应该显式触发：

```text
$agent-retrospective
```

普通的“帮我复盘”“总结一下”不应该自动触发该 skill。

## 默认输出

默认会在当前 agent 工作目录下写入私有数据目录：

```text
.agent-retrospective-data/
```

核心输出包括：

- `agent_retrospective.md`：长期总复盘。
- `reports/runs/YYYY-MM-DD-HHMM.md`：每次运行报告。
- `reports/weekly/YYYY-Www.md`：当前周报。
- `reports/yearly/YYYY.md`：当前年报。
- `state/state.json`：增量状态索引。
- `state/session_summaries.jsonl`：结构化 session 摘要。
- `state/review_runs.jsonl`：每次运行日志。

## 推荐仓库拆分

- `agent-retrospective`：公开仓库，只放 skill、CLI、文档和架构说明。
- `agent-retrospective-data`：私有仓库，放生成的复盘数据和状态文件。

公开仓库的 `.gitignore` 已经忽略 `.agent-retrospective-data/`，避免误提交个人数据。

## 直接运行

```bash
python3 src/agent_retrospective/cli.py
```

指定私有数据目录：

```bash
AGENT_RETROSPECTIVE_ROOT=/path/to/private-data python3 src/agent_retrospective/cli.py
```

当前已实现的数据源是 Codex：

```bash
python3 src/agent_retrospective/cli.py --source codex --codex-home ~/.codex
```

## 多 Agent 扩展思路

当前 CLI 已预留 `--source` 参数。现在只支持 `codex`，后续可以把不同 agent 的原始数据读取逻辑做成 adapter，但统一输出到同一套 summary schema。

建议的 adapter 输出字段包括：

- `session_id`
- `source`
- `cwd`
- `title`
- `created_at`
- `updated_at`
- `user_intents`
- `command_samples`
- `function_call_counts`
- `signals`
- `outcomes`

更详细的架构说明见 [references/multi-agent-architecture.md](references/multi-agent-architecture.md)。

## 隐私边界

- 原始 session 不复制进复盘仓库。
- 公开 skill 仓库不提交生成数据。
- 发现 token、password、cookie、API key 等敏感信息时，用 `[REDACTED_SECRET]` 形式遮蔽。
- 私有数据仓库仍会包含项目名、路径、时间线和任务背景，应保持 private。
