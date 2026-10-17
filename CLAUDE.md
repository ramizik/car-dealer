# CLAUDE.md

## Context
6-hour hackathon. Theme: persistent agent teams you can walk away from. Build on Crusoe Managed Inference (OpenAI-compatible API) with NVIDIA Nemotron. Optional sponsors: NVIDIA NemoClaw, You.com Search/Research API.

Problem statements (pick one to push hardest, keep the others cheap):
1. **Done Means Done** - agent writes its own definition of done, verifies with tests/independent verifier agents, detects drift/loops, decides continue / re-plan / stop / ping human. (Currently implemented in `backend/loop.py`.)
2. **Shared Brain** - shared memory every agent reads before work and updates after; lean, conflict-free, with measurable quality gain. (Seeded in `backend/memory.py`.)
3. **Version N+1** - team rewrites its own prompts/playbooks after each run, keeps a change only if it scores better on unseen tasks.

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
- `agents/` - shared team skills (`agents/skills/`) and plans (`agents/plans/`). Read `agents/skills/crusoe-recursive-agents-hackathon/SKILL.md` before any Crusoe/LLM work.

## Commands
- Backend: `cd backend && uvicorn main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev`

## Rules
- Keep it minimal. No abstractions beyond what the demo needs.
- Demo safety: keep mock/cached fallback working; never show a blank screen or stack trace.
- Never commit `.env` or keys.
- No spec/plan docs in the repo; scratch notes go in `%TEMP%`.
- Add a measurable score (before/after, pass rate) to anything claimed as improvement.
