**语言:** [English](README.md) | 简体中文

# agent-retrospective 中文说明

`agent-retrospective` 是一个显式触发的 Codex skill，也是一个本地优先的增量复盘工具。它把本机 agent session 维护成一个私有 LLM wiki：原始 session 不复制，私有数据仓库里持续更新索引、结构化摘要、运行报告、周报、年报和长期总复盘。

## 适用场景

- 你想定期复盘自己如何使用 Codex 或其他 AI coding agent。
- 你希望复盘是增量的，而不是每次重新扫描和重写全部历史。
- 你希望保留真实项目名、路径和任务背景，但不想把这些内容放进公开仓库。
- 你希望 agent 尽量用原生读文件和分析能力，而不是被固定工具流程限制。

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

- `index.md`：私有 wiki 导航。
- `log.md`：可读的维护时间线。
- `agent_retrospective.md`：长期总复盘。
- `reports/runs/YYYY-MM-DD-HHMM.md`：每次运行报告。
- `reports/weekly/YYYY-Www.md`：当前周报。
- `reports/yearly/YYYY.md`：当前年报。
- `state/state.json`：增量状态索引。
- `state/session_summaries.jsonl`：结构化 session 摘要。
- `state/review_runs.jsonl`：每次运行日志。

## 推荐仓库拆分

- `agent-retrospective`：公开仓库，只放 skill、CLI 和用户文档。
- `agent-retrospective-data`：私有仓库，放生成的复盘数据和状态文件。

公开仓库的 `.gitignore` 已经忽略 `.agent-retrospective-data/`，避免误提交个人数据。

## 直接运行

```bash
python3 src/agent_retrospective/cli.py
```

默认数据目录固定为当前 workspace 下的 `.agent-retrospective-data/`。这是脚本行为，不只是提示词约定。只有你想把私有数据放到别的仓库时才需要覆盖。

指定私有数据目录：

```bash
AGENT_RETROSPECTIVE_ROOT=/path/to/private-data python3 src/agent_retrospective/cli.py
```

当前内置来源是 Codex：

```bash
python3 src/agent_retrospective/cli.py --source codex --codex-home ~/.codex
```

默认会尝试这些来源；不存在的目录会自动跳过：

- Codex：`~/.codex`
- Claude Code：`~/.claude/projects`
- Cursor：`~/.cursor`
- OpenCode：`~/.opencode`

## 多 Agent 安装

Codex：

```bash
mkdir -p ~/.codex/skills
cp -R /path/to/agent-retrospective ~/.codex/skills/agent-retrospective
```

Claude Code：

```bash
cp AGENTS.md CLAUDE.md /path/to/project/
```

Cursor / OpenCode：

- 把本仓库加入项目或用户级 agent 上下文。
- 让 agent 读取 `SKILL.md` 和 `scripts/run_review.sh`。
- 显式触发 `agent-retrospective` 工作流。

## 增量逻辑

脚本会在 `state/state.json` 中记录 session 指纹，在 `state/session_summaries.jsonl` 中保存结构化摘要。

session 的状态 key 由来源、session id 和路径组成，避免复制或 fork 出来的 session 互相覆盖。如果旧 session 追加了新的用户输入，通常会导致文件 `mtime` 或 `size` 改变，因此会被识别为变更。仍在活跃变化的 session 会暂时跳过，但不会推进已存指纹，下一次稳定运行时仍会被继续分析。

每次运行都会刷新当前周报和年报；不需要自动定时，用户触发 `$agent-retrospective` 就是复盘时机。如果跨周或跨年，脚本会再刷新上一周或上一年的报告，作为周期归档。

## 隐私边界

- 原始 session 不复制进复盘仓库。
- 公开 skill 仓库不提交生成数据。
- 发现 token、password、cookie、API key 等敏感信息时，用 `[REDACTED_SECRET]` 形式遮蔽。
- 私有数据仓库仍会包含项目名、路径、时间线和任务背景，应保持 private。
