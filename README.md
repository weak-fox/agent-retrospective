**Language:** English | [简体中文](README.zh-CN.md)

# agent-retrospective

Explicit-only Codex skill and local-first CLI for maintaining a private LLM wiki over AI agent session history.

`agent-retrospective` turns local agent sessions into a continuously updated reflection knowledge base. Raw sessions stay where each agent stores them; this project maintains the private wiki layer: indexes, structured summaries, run reports, weekly reports, yearly reports, and a long-lived synthesis.

## Why This Exists

- Incremental review: process new or changed sessions without rereading everything.
- Explicit trigger: run only when the user names `$agent-retrospective`.
- Agent-native analysis: guide the workflow without restricting how agents inspect files.
- Local-first privacy: raw sessions stay local and generated reports live in a private data directory.
- Wiki layer: maintain `index.md`, `log.md`, reports, and structured summaries so future runs have context.

## Quick Start

Install or copy this folder into your Codex skills directory, then invoke:

```text
$agent-retrospective
```

You can also run the CLI directly:

```bash
python3 src/agent_retrospective/cli.py
```

Use a custom private data location:

```bash
AGENT_RETROSPECTIVE_ROOT=/path/to/private-data python3 src/agent_retrospective/cli.py
```

By default, the CLI uses the fixed private data directory `.agent-retrospective-data/` under the current workspace. This is code behavior, not just prompt guidance. Override it only when you want a different private data repository.

The built-in source profiles are tried by default:

- Codex: `~/.codex`
- Claude Code: `~/.claude/projects`
- Cursor: `~/.cursor`
- OpenCode: `~/.opencode`

Only existing session directories are scanned. You can narrow the run:

```bash
python3 src/agent_retrospective/cli.py --source codex
```

## Install In Agents

Codex:

```bash
mkdir -p ~/.codex/skills
cp -R /path/to/agent-retrospective ~/.codex/skills/agent-retrospective
```

Claude Code:

```bash
cp AGENTS.md CLAUDE.md /path/to/project/
```

Cursor / OpenCode:

- Add this repository to the project or user-level agent context.
- Point the agent at `SKILL.md` and `scripts/run_review.sh`.
- Invoke the workflow explicitly as `agent-retrospective`.

## Repository Split

Recommended setup:

- Public skill repository: `agent-retrospective`
- Private generated-data repository: `agent-retrospective-data`

The private data repository can include local paths, project names, timelines, remote environment clues, and personal workflow summaries. Keep it private.

## Directory Layout

```text
agent-retrospective/
├── AGENTS.md
├── CLAUDE.md
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── agents/
│   └── openai.yaml
├── scripts/
│   └── run_review.sh
└── src/
    └── agent_retrospective/
        ├── __init__.py
        └── cli.py
```

Generated private data is ignored by this repository:

```text
.agent-retrospective-data/
├── index.md
├── log.md
├── agent_retrospective.md
├── reports/
│   ├── runs/YYYY-MM-DD-HHMM.md
│   ├── weekly/YYYY-Www.md
│   └── yearly/YYYY.md
└── state/
    ├── state.json
    ├── session_summaries.jsonl
    └── review_runs.jsonl
```

## How Incremental Review Works

The CLI maintains fingerprints in `state/state.json` and structured summaries in `state/session_summaries.jsonl`.

A session is keyed by source, session id, and path. This keeps copied or forked sessions from overwriting each other. A session is treated as changed when its stored fingerprint differs from the current file metadata. Older sessions with newly appended user input are therefore picked up as changes. Active sessions that are still changing are skipped temporarily without advancing their stored fingerprint, so they remain pending for a later stable run.

Each run refreshes:

- `index.md`: agent-readable map of the private wiki
- `log.md`: human-readable maintenance timeline
- `agent_retrospective.md`: long-lived synthesis
- `reports/runs/YYYY-MM-DD-HHMM.md`: current run report
- `reports/weekly/YYYY-Www.md`: current week report
- `reports/yearly/YYYY.md`: current year report

When a run crosses into a new week or year, the previous week or year report is refreshed once more as a finalized period summary.

## Privacy Model

- Do not copy raw session files into this repository.
- Do not commit generated data to the public skill repository.
- Secret-like strings are redacted before summary output.
- Generated data is intentionally detailed and should live in a private repository.
