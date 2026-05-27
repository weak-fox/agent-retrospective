---
name: agent-retrospective
description: Explicit-only workflow for incrementally reviewing local agent sessions into the current workspace's private retrospective directory. Use only when the user explicitly names `$agent-retrospective`, says to use the `agent-retrospective` skill, or asks to run the agent retrospective skill. Do not trigger for ordinary review, recap, retrospective, or summary requests unless this skill name is explicitly mentioned.
metadata:
  short-description: Incrementally review local agent sessions
---

# Agent Retrospective

This skill maintains an incremental retrospective over local agent sessions while keeping generated personal data in the current workspace's private `.agent-retrospective-data/` repository.

## Trigger Policy

Use this skill only when the user explicitly invokes `$agent-retrospective` or names `agent-retrospective skill`.

Do not infer this skill from generic words like review, recap, summary, retrospective, weekly report, or self-improvement.

## Default Locations

- Skill/source workspace: the repository containing this `SKILL.md`
- Private data workspace: `.agent-retrospective-data/` under the current agent working directory
- Script: `scripts/agent_retrospective.py`
- Default Codex data source: `$HOME/.codex`

Override the private data workspace with:

```bash
AGENT_RETROSPECTIVE_ROOT=/path/to/private-data python3 scripts/agent_retrospective.py
```

## Workflow

1. Run the incremental scanner from the skill/source workspace:

   ```bash
   python3 scripts/agent_retrospective.py
   ```

2. Read the JSON summary printed by the script and report changed counts.

3. Point the user to updated files in the private workspace:
   - `agent_retrospective.md`
   - latest `reports/runs/YYYY-MM-DD-HHMM.md`
   - current `reports/weekly/YYYY-Www.md`
   - current `reports/yearly/YYYY.md`

4. If the script reports no changed sessions, say that existing summaries were reused and no stable session was reprocessed.

## Privacy Rules

- Preserve project names, local paths, timestamps, thread titles, remote environment context, and workflow evidence in the private workspace data.
- Never write complete API keys, tokens, passwords, cookies, authorization headers, or reconstructable secret byte arrays into any output.
- If sensitive material appears in a prompt, keep only the fact that a secret was present and replace the value with `[REDACTED_SECRET]`.
- Do not copy raw session JSONL files into the review workspace.
- Do not commit generated data to the open-source skill repository.

## Output Expectations

Keep the user-facing response short:

- Total sessions scanned
- New, changed, active-skipped, unchanged counts
- Updated private-data file links
- Any verification warnings
