# Demo script: Joe's Auto, a used-car agent team with a shared brain

**Length:** 4 minutes. **Track:** Shared Brain. **One line:** every agent reads memory before it works and writes after; memory has three layers, and the team measurably negotiates better with it on.

## The memory story (say this, show this)

| Layer | What it holds | Who reads it | Where it shows |
|---|---|---|---|
| 1. Private chats | Raw talk with each seller, one Markdown file per seller (`data/conversations/`). Phones masked. Closed and stamped with the outcome when the deal ends. Plus a short "chat gist" in the brain marked private. | Only the agent that had the chat (negotiator) | Insights > Shared brain > "1. Private chats" count; feed lines "(private to negotiator)" |
| 2. Shared brain | One deterministic result line per deal: `[SUCCESS] closed $9,250 vs ask $11,000 in 4 rounds; comps anchor worked`. Plus market values, dealer rules, tactic win counts. Append-only log, conflict-free merge. | Every agent: scout, appraiser, negotiator, sales desk, logistics, merchandiser | Feed "Saved to memory: [...]"; "2. Shared brain" count; "Sellers and buyers", "Market" cards |
| 3. Long-term (lessons + vector store) | Librarian runs every 3 deals: tactic with 3+ tries becomes a lesson; a failure seen in 2+ deals becomes a MISTAKES.md line; lessons, mistakes and every deal result line go into an embedded vector store (`data/vectors/memories.jsonl`, no server). Then compacts the brain log, only if recall is byte-identical before and after. Raw chats and private gists never reach it. | Negotiator: lessons + top mistakes in its prompt, plus the 3 most similar past deals from the vector store before each talk. Mistakes in the store are negotiator-only. | Feed "N similar past deals" (expand to see them); "Memory tidied: 215 -> 211 entries, 2 lessons, 1 new mistakes, 4 long-term memories"; "3. Long-term lessons" card shows vector count |

The owner's own input (onboarding answers, approve/decline decisions) lands in the shared brain `dealer` scope, so every agent follows the owner's rules ("Your rules" card).

**Pitch line for the vector store:** "Every finished deal becomes a searchable memory. Before the next talk, the buyer pulls the closest past deals, same car, same kind of seller, so the whole team learns from any one agent's experience. It's one file, no database server, and it respects who may see what."

**Embeddings:** with `NVIDIA_API_KEY` in `backend/.env` the store uses NVIDIA `nv-embedqa-e5-v5`; without it, a local hashing embedding (works offline, weaker matches: live hit scored 0.15 vs a 0.15 cutoff). Add the key before the demo for better "similar past deals" hits, and say "NVIDIA embeddings" on stage only if `GET /brain` -> `tiers.vectors.embedders` shows the NVIDIA model.

## Before the demo (T-10 min)

1. `cd backend && python test_memory_tiers.py` -> `memory tiers ok: ...` (offline, 2 s).
2. `cd backend && python test_brain.py` -> `brain ok: ...`.
3. Save the current brain: `python -c "import brain; brain.snapshot('backup')"`.
4. Fresh stage: `python reset_demo.py cold`. Clears deals, chat files and the vector store. Careful: the first time, it also wipes the live brain to make the empty `cold` snapshot, so do step 3 first. It does not clear `skills/buyer/outreach/MISTAKES.md`; delete that by hand for a zero "Known mistakes" card. `python reset_demo.py warm` loads the trained brain instead (vector store refills at the first librarian run).
5. Start backend `uvicorn main:app --port 8000`, frontend `npm run dev`. Check `GET /health` shows `"llm_live": true`.
6. Fallback if Crusoe is slow or 429s: `DEMO_MODE=1` (cached You.com), and the warm brain. Backup video ready.

## Script and expected milestones

| Clock | Say | Do | Expected on screen (milestone) |
|---|---|---|---|
| 0:00 | "Joe runs a used-car lot. Sourcing, haggling, shipping, listing eats his day. This team does it while he walks away." | Open Shift tab, cold brain. | Insights shows 0 lessons, 0 mistakes. |
| 0:20 | "I tell it my rules once." | Show Onboarding / Your rules (min profit $1,500, max buy). | "Your rules" card has dealer decisions. **M1: owner input is in the shared brain.** |
| 0:35 | "Start a 5-deal shift." | Shift > 5 deals > Start shift. | Phase goes scouting -> sourcing. Scout finds real You.com listings, appraiser writes `market / value:...` with low/mid/high. **M2: real listing valued, written to memory.** |
| 1:00 | "Before it talks, the negotiator reads memory, including similar past deals." | Point at feed. | `negotiator recall N memories`, `1 similar past deals` (expands to `[SUCCESS] 2008 Toyota RAV4: closed $8,850 vs ask $10,600 ...`), then `Chose tactic ...`. Similar deals only appear after the first librarian run (deal 3+) on a cold brain; warm brain shows them from deal 1. **M3: read-before-work visible, incl. vector recall.** |
| 1:20 | "After the talk, the raw chat stays private. Only one result line is shared." | Point at feed. | `Saved to memory: [SUCCESS] closed $9,250 vs ask $11,000 ...` and `(private to negotiator) ... chat gist: ...`. **M4: two layers, shared vs private.** |
| 1:45 | "Sales desk reads the same shared brain and protects Joe's margin." | Point at a dropped deal. | `Dropped D-203: sales desk: profit -$330 is under your $1,500 minimum`. **M5: a different agent acted on shared memory and the owner's rule.** |
| 2:00 | "A buy needs my OK." | Decisions card > Approve. | Deal moves bought -> in transit -> delivered -> listed. Storefront (`/storefront`) shows the merchandiser's listing. **M6: walk-away pipeline runs in the background.** |
| 2:30 | "Every 3 deals the librarian turns experience into lessons." | Insights > Shared brain. | Feed `Memory tidied: X -> Y entries, N lessons`. Cards: `haggler sellers -> walk away threat wins 4/5`, `Repeated miss: seller walked away`. Log smaller, recall unchanged. **M7: memory gets smaller and smarter, conflict-free.** |
| 3:00 | "Does it actually help? Same agents, brain off vs on, on 10 sellers they've never seen." | Insights > Brain off vs on. | Saved vs asking **13.7% -> 16.4%** (seed 2: 15.4% -> 19.9%), rounds **3.9 -> 2.9**, scams blocked 1/1 both. **M8: measured gain.** |
| 3:30 | "It runs inside NemoClaw. A scam seller asks for payment on a fake site; the sandbox blocks it." | `openshell term` on droplet. | Blocked egress line. **M9: NVIDIA safety moment.** |
| 3:50 | "Joe walks away; the team keeps working and keeps learning." | Shift > Until I stop it. | Close. |

## If something breaks live

- Feed stalls (Crusoe 429): keep talking over M7/M8, they are already on screen from the warm brain. `POST /shift/stop`.
- Blank Insights: backend down, restart it; state reloads from `data/state.json`.
- No gist line: no LLM key or the fast model failed. Shared `[STATUS]` line still shows; say "private notes stay with the negotiator".

## Verified 2026-10-17 (live, Nemotron on Crusoe, 3-deal shift)

- D-201 dropped (seller walked away) -> `[FAILED]` shared + private gist.
- D-202 closed $9,250 vs $11,000 ask -> `[SUCCESS]` shared + private gist, waits for owner OK.
- D-203 dropped by sales desk (profit under $1,500 minimum) -> `[FAILED]`. Live run wrote a made-up gist here (re-read an old chat); fixed after, now no talk means no gist (checked in `test_memory_tiers.py`, not re-run live).
- Librarian: 204 -> 187 entries, 2 lessons. Insights "Memory layers" panel renders all four cards.
- Second run after the vector store landed: D-205 2008 RAV4 recalled `1 similar past deals` (a past RAV4 close) before talking, then closed $8,850 vs $10,600. Librarian: 215 -> 211 entries, 1 new mistake, 4 long-term memories. Insights shows 19 vector memories.
- `python test_memory_tiers.py` (offline) checks: phone masking, chat closed with outcome, shared vs private recall, no gist without talk, lesson and MISTAKES.md line, vector search finds the past deal, mistakes hidden from other agents, no gists in the vector store, compaction keeps recall identical.
