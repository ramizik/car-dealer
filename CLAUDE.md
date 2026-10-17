# CLAUDE.md

## Context
6-hour hackathon. Theme: persistent agent teams you can walk away from. Build on Crusoe Managed Inference (OpenAI-compatible API) with NVIDIA Nemotron. Optional sponsors: NVIDIA NemoClaw, You.com Search/Research API.

Track: **Shared Brain only** - shared memory every agent reads before work and updates after; lean, conflict-free, with measurable quality gain. Product: local agent team for used-car dealers (source, appraise, negotiate, buy, ship, list, sell). Pitch: `docs/project-idea.md`. Build plan: `agents/plans/roadmap.md`.

## Execution speed (hard time limit, follow strictly)
- Work directly on `main`. No branches, no worktrees, no PRs.
- Commit by yourself after each working change. Do not ask for confirmation. Run `git pull --rebase` before committing to stay in sync with teammates.
- Do not ask the human to confirm routine steps (edits, installing deps listed in requirements/package.json, running dev servers, commits). Stop and ask only for: secrets/keys, deleting or rewriting someone else's work, anything that spends real money or contacts real people.
- No long-running checks. No full test suites, full builds, or watch modes unless asked. One quick smoke check (single curl, single test file) capped at about 1 minute, then move on. Run servers in the background, never wait on them.
- Keep sessions short: one task, finish, commit, stop. No broad exploration or research; grep for what you need.
- Skip brainstorming, spec and plan rituals. The plan already exists in `agents/plans/roadmap.md`.
- Subagents: always use model `haiku` (Haiku 5.5, `claude-haiku-5-5`). Spawn only when parallel work clearly saves time.

## Role
Act as a blunt hackathon CTO. Optimize for speed, demo stability, simplicity, judge-visible impact. Cut anything not visible in the demo. Always ask: can this fail live? what is the fastest working version?

## Stack
- Backend: FastAPI, single service, in `backend/`. In-memory/JSON storage only. No DB, no auth, no microservices.
- Frontend: Vite + React + TypeScript in `frontend/`. useState only.
- LLM: `backend/llm.py` wraps Crusoe via the `openai` SDK (`CRUSOE_BASE_URL`, `CRUSOE_MODEL`). Mock mode when `CRUSOE_API_KEY` is empty.

## Layout
- `backend/loop.py` - define-done -> work -> verify -> decide loop
- `backend/memory.py` - shared brain (JSON file, capped lessons)
- `backend/main.py` - REST: `GET /health`, `POST /run`, `GET /memory`
- `frontend/src/App.tsx` - goal input, trace view, memory view
- `agents/plans/` - shared team plans (`roadmap.md`).
- `.claude/skills/` - shared team skills, auto-loaded by Claude Code and Cursor (see its README). Read `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md` before any Crusoe/LLM work; `nemoclaw-user-guide` before NemoClaw/OpenShell work.

## Commands
- Backend: `cd backend && uvicorn main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev`

## Rules
- Keep it minimal. No abstractions beyond what the demo needs.
- Demo safety: keep mock/cached fallback working; never show a blank screen or stack trace.
- Never commit `.env` or keys.
- Shared plans live only in `agents/plans/`. No other spec/plan docs in the repo; scratch notes go in `%TEMP%`.
- Add a measurable score (before/after, pass rate) to anything claimed as improvement.
