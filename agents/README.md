# agents/

Shared agent context for the team. Checked in on purpose.

## Layout
- `plans/` - shared plans and task breakdowns the team is actively working from. One file per plan, short, delete when done. Current: `plans/roadmap.md`.
- Skills live in `.claude/skills/` (not here), so Claude Code and Cursor auto-load them with no setup. See `.claude/skills/README.md`.

## Rules
- No keys, tokens, or `.env` contents in any file here.
- Keep files lean; this folder gets read into agent context.
