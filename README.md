# agent-retrospective

Explicit-only Codex skill and local-first CLI for incremental AI agent session retrospectives.

`agent-retrospective` turns local agent history into a private, continuously updated reflection knowledge base. It is designed for developers who want to review how they use Codex today, while leaving room for Claude Code, Cursor CLI, OpenCode, and other agent sources later.

## Why This Exists

- Incremental review: only new or changed sessions are summarized after the first run.
- Explicit trigger: the skill runs only when the user names `$agent-retrospective`.
- Local-first privacy: raw sessions stay in the agent's local data directory.
- Private output repository: generated reports live in `.agent-retrospective-data/` by default.
- Multi-agent direction: the storage model and CLI expose a `--source` adapter boundary.

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

The current implemented source adapter is Codex:

```bash
python3 src/agent_retrospective/cli.py --source codex --codex-home ~/.codex
```

## Repository Split

Recommended setup:

- Public skill repository: `agent-retrospective`
- Private generated-data repository: `agent-retrospective-data`

The generated data repository can include local paths, project names, time lines, remote environment clues, and personal workflow summaries. Keep it private.

## Directory Layout

```text
agent-retrospective/
├── SKILL.md                         # Codex skill trigger policy and workflow
├── README.md                        # English project overview
├── README.zh-CN.md                  # Chinese project overview
├── agents/
│   └── openai.yaml                  # Codex UI metadata
├── references/
│   └── multi-agent-architecture.md  # Adapter and data-model notes
├── scripts/
│   └── run_review.sh                # Stable wrapper used by the skill
└── src/
    └── agent_retrospective/
        ├── __init__.py
        └── cli.py                   # Incremental scanner and report generator
```

Generated private data is ignored by this repository:

```text
.agent-retrospective-data/
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

## Source Adapter Direction

Today, `--source codex` reads:

- `$HOME/.codex/sessions/**/*.jsonl`
- `$HOME/.codex/archived_sessions/**/*.jsonl`
- `$HOME/.codex/state_5.sqlite`
- `$HOME/.codex/session_index.jsonl`
- `$HOME/.codex/generated_images/`

Future adapters should normalize other agents into the same summary fields: `session_id`, `source`, `cwd`, `title`, `created_at`, `updated_at`, `user_intents`, `tool/function counts`, `signals`, and privacy-redacted evidence.

See [references/multi-agent-architecture.md](references/multi-agent-architecture.md) for the extension model.

## Privacy Model

- Do not copy raw session JSONL files into this repository.
- Do not commit generated data to the public skill repository.
- Secret-like strings are redacted before summary output.
- Generated data is intentionally detailed and should live in a private repository.

## Chinese Docs

中文说明见 [README.zh-CN.md](README.zh-CN.md)。
