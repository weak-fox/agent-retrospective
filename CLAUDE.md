# Claude Code Instructions

This repository follows the cross-agent rules in [AGENTS.md](AGENTS.md).

Claude Code agents should follow those rules first, especially:

- Ask before committing, pushing, deleting data, or changing GitHub metadata.
- Keep `.agent-retrospective-data/` out of the public repository.
- Use native file and shell inspection freely; do not assume a specific command is required unless the repository script is the intended stable entry point.
- Keep skill instructions concise and explicit-trigger only.

Repository entry points:

- Skill instructions: `SKILL.md`
- Stable review wrapper: `scripts/run_review.sh`
- CLI implementation: `src/agent_retrospective/cli.py`
