# agent-retrospective

Explicit-only skill for incremental local agent session retrospectives.

This repository is intended to be open-source safe. Generated personal retrospective data is written inside the current agent workspace by default:

```text
.agent-retrospective-data/
```

Recommended repository split:

- Public skill repository: `agent-retrospective`
- Private generated-data repository: `agent-retrospective-data`

Use the skill explicitly when you want to update the review:

```text
$agent-retrospective
```

Or run the scanner directly:

```bash
python3 scripts/agent_retrospective.py
```

Override the private output location when needed:

```bash
AGENT_RETROSPECTIVE_ROOT=/path/to/private-data python3 scripts/agent_retrospective.py
```

Private workspace outputs:

- `agent_retrospective.md`
- `reports/runs/`
- `reports/weekly/`
- `reports/yearly/`
- `.agent-retrospective-data/state/session_summaries.jsonl`
- `.agent-retrospective-data/state/state.json`

Open-source repository contents:

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/agent_retrospective.py`
- `scripts/run_review.sh`

Current source support:

- Codex local sessions from `$HOME/.codex`
- The output model is intentionally agent-neutral so additional agent sources can be added later.
