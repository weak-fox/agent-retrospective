# Agent Instructions

These rules apply to all AI agents working in this repository.

## Change Control

- Do not commit, push, create releases, edit GitHub metadata, or delete data unless the user explicitly confirms that action.
- For structural changes, show the intended diff or concise change plan before applying it when the user has asked for confirmation.
- Keep public skill code separate from generated private data.

## Repository Boundaries

- Public repository: skill source, scripts, and user-facing docs.
- Private data directory: `.agent-retrospective-data/`.
- Never commit `.agent-retrospective-data/`, raw session logs, or generated personal reports to the public repository.
- Keep generated data private because it may include project names, paths, timelines, infrastructure clues, and workflow summaries.

## Skill Design

- Keep `SKILL.md` concise and explicit-trigger only.
- Do not trigger this skill for generic review, recap, retrospective, summary, weekly report, or self-improvement requests unless the user names `$agent-retrospective` or the skill name.
- Prefer guidance over command prescriptions. Do not restrict which native shell/file tools an agent may use unless a repository-provided script is required for correctness.
- Let agents use their native ability to read, inspect, and summarize session data.
- Use scripts only for deterministic bookkeeping such as discovery, fingerprints, state files, privacy redaction, and stable output paths.

## Incremental Review Rules

- Treat a session as changed when its fingerprint changes, including older sessions with newly appended user input.
- Do not advance stored fingerprints for active or volatile sessions unless their summaries are also refreshed.
- Preserve enough surrounding context for changed sessions so summaries are not detached from prior goals, decisions, and outcomes.
- When possible, compare changed sessions against historical summaries before revising long-term conclusions.

## Documentation

- Keep README language links at the top of each README.
- Keep installation and usage docs practical and short.
- Do not add a separate multi-agent architecture document unless the user explicitly asks for one.
