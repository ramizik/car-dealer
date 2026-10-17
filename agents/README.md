# agents/

Shared agent context for the team. Checked in on purpose (`.claude/` is gitignored, so anything here is what everyone sees).

## Layout
- `skills/<name>/SKILL.md` - reusable skills (frontmatter `name` + `description`, then instructions). Point your agent at the file or copy/symlink the folder into your local `.claude/skills/` to auto-load.
- `plans/` - shared plans and task breakdowns the team is actively working from. One file per plan, short, delete when done.

## Skills
- `skills/crusoe-recursive-agents-hackathon/` - source of truth for the event and Crusoe Managed Inference: endpoint, model IDs, rate limits, reasoning toggles, troubleshooting. Read before touching `backend/llm.py`.

## Rules
- No keys, tokens, or `.env` contents in any file here.
- Keep files lean; this folder gets read into agent context.
