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
| 0:00 | "Joe runs a used-car lot. Sourcing, haggling, shipping, listing eats his day. This team does it while he walks away." | Shift page, cold brain. | Stats row at 0, "Recent memories" empty. |
| 0:15 | "I tell it my rules once." | Setup: min profit $1,500, max buy. | Rules saved to the `dealer` scope. **M1: owner input is in the shared brain.** |
| 0:30 | "One button: a full 8-hour shop day in 5 minutes, four cars at once." | Sidebar > **Start Demo**. | Progress bar runs. Findings: real Craigslist listings, You.com valuations with low/mid/high. **M2: real listing valued, written to memory.** |
| 0:55 | "Before it talks, every agent reads the shared brain. After, it writes back." | Point at stats row and "Recent memories". | "Memory reads" / "Memory writes" climb; memories show scope chips (market, party, playbook). Decisions: `Chose tactic "comps anchor" for a haggler seller`. **M3: read-before, write-after, visible.** |
| 1:15 | "Open any deal: you see exactly what it remembered on each turn." | Click a deal card. | Chat with "Recalled:" chips under agent messages, "Saved to team memory" list, You.com citation links. **M4: recall is per turn and auditable.** |
| 1:40 | "One seller phones in live. I answer as the seller." | Deal drawer with the turn banner: record by mic or type. | Agent voice (Magpie) plays, my answer is transcribed (Parakeet), the negotiator counters. **M5: NVIDIA speech in the loop.** |
| 2:10 | "Clear wins it buys alone. Borderline ones and every sale wait for me." | Decisions > Approve a buy, then Sell on a sale. | Deal moves bought -> in transit -> listed -> sold; profit shows in stats. **M6: walk-away pipeline asks only when it must.** |
| 2:35 | "A different agent acts on the same memory." | Point at a dropped deal in Decisions. | `sales desk: profit -$330 is under your $1,500 minimum`. Librarian line `Memory tidied: X -> Y entries, N lessons`. **M7: shared, conflict-free, gets smaller.** |
| 3:00 | "Does memory actually help? Same agents, brain off vs on, 10 sellers they've never seen." | "Measured: brain off vs on" card under Recent memories. | Saved off asking **13.7% -> 16.4%** (seed 2: 15.4% -> 19.9%), rounds **3.9 -> 2.9** (26% fewer model turns per car), scams blocked both. **M8: measured gain.** |
| 3:25 | "It runs inside NemoClaw. A scam seller sends a payment link; the sandbox blocks it." | `openshell term` on droplet; red "blocked" row in the feed. | Blocked egress line. **M9: NVIDIA safety moment.** |
| 3:50 | "Joe walks away; the team keeps working and keeps learning." | Leave the shift running. | Close. |

## If something breaks live

- Feed stalls (Crusoe 429): after 2 failed calls the app switches to template messages for 60 s and shows a "Degraded" banner; prices and memory keep working. Say "it degrades instead of dying" and keep going.
- Live seller never answers: it falls back to the simulated seller after 120 s.
- Blank page: backend or tunnel down, restart it; state reloads from `data/state.json`.
- No gist line: no LLM key or the fast model failed. Shared `[STATUS]` line still shows; say "private notes stay with the negotiator".

## Verified 2026-10-17 (live, Nemotron on Crusoe, 3-deal shift)

- D-201 dropped (seller walked away) -> `[FAILED]` shared + private gist.
- D-202 closed $9,250 vs $11,000 ask -> `[SUCCESS]` shared + private gist, waits for owner OK.
- D-203 dropped by sales desk (profit under $1,500 minimum) -> `[FAILED]`. Live run wrote a made-up gist here (re-read an old chat); fixed after, now no talk means no gist (checked in `test_memory_tiers.py`, not re-run live).
- Librarian: 204 -> 187 entries, 2 lessons. Insights "Memory layers" panel renders all four cards.
- Second run after the vector store landed: D-205 2008 RAV4 recalled `1 similar past deals` (a past RAV4 close) before talking, then closed $8,850 vs $10,600. Librarian: 215 -> 211 entries, 1 new mistake, 4 long-term memories. Insights shows 19 vector memories.
- `python test_memory_tiers.py` (offline) checks: phone masking, chat closed with outcome, shared vs private recall, no gist without talk, lesson and MISTAKES.md line, vector search finds the past deal, mistakes hidden from other agents, no gists in the vector store, compaction keeps recall identical.
