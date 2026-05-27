# Multi-Agent Architecture Notes

This project should stay useful as a Codex skill while avoiding Codex-only assumptions in its public data model.

## Current Shape

- `SKILL.md` stays concise because it is loaded into the agent context only after explicit invocation.
- `scripts/run_review.sh` is the stable wrapper entry point.
- `src/agent_retrospective/cli.py` contains the current Codex scanner and report generator.
- `references/` stores design notes that are useful to maintainers but should not be loaded unless needed.

This follows common skill project practice: keep the skill body small, put deterministic behavior in scripts, and keep detailed documentation outside `SKILL.md`.

## Adapter Boundary

The CLI exposes:

```bash
python3 src/agent_retrospective/cli.py --source codex
```

Only `codex` is implemented today. Future sources should add a scanner that returns normalized session records instead of changing the report layer.

Recommended adapter contract:

```text
discover_sessions(source_home) -> list[SessionFingerprint]
summarize_session(fingerprint, metadata) -> SessionSummary
```

`SessionFingerprint` should include:

- `session_id`
- `source`
- `path`
- `mtime_ns`
- `size_bytes`

`SessionSummary` should include:

- `session_id`
- `source`
- `cwd`
- `title`
- `created_at`
- `updated_at`
- `user_intents`
- `agent_messages`
- `command_samples`
- `event_counts`
- `function_call_counts`
- `signals`
- `outputs`
- `privacy_notes`

## Source-Specific Inputs

Codex currently reads:

- JSONL sessions under `~/.codex/sessions`
- archived JSONL sessions under `~/.codex/archived_sessions`
- `~/.codex/state_5.sqlite`
- `~/.codex/session_index.jsonl`
- generated image counts under `~/.codex/generated_images`

Future adapters can read Claude Code, Cursor CLI, OpenCode, or other local agent history as long as they normalize into the same summary schema.

## Privacy Rules

Adapters must redact secrets before writing summaries. Keep raw session data out of the generated data repository.

Do not write complete values for:

- API keys
- tokens
- passwords
- cookies
- authorization headers
- reconstructable byte-array secrets

## Repository Split

Use two repositories:

- Public: `agent-retrospective`, containing the skill and source code.
- Private: `agent-retrospective-data`, containing generated retrospectives and state.

The public repository must ignore `.agent-retrospective-data/`.
