# Dealer: an AI agent team for used-car dealers, with a shared brain

A team of Nemotron agents finds real used-car listings, appraises them with cited sources, negotiates with sellers, asks the owner to approve, then lists and sells the car. Every agent reads a **shared brain** before it works and writes to it after. On sellers it has never seen, the team negotiates measurably better and faster than the same agents with the brain off.

**Track:** Shared Brain. **Sponsors used:** Crusoe Managed Inference, NVIDIA Nemotron, NVIDIA NemoClaw / OpenShell, You.com APIs, NVIDIA Speech (Parakeet, Magpie) and embeddings.

**Status (2026-10-17):** the full pipeline runs in code, and the brain OFF vs ON eval is measured. The live seller flow (a person answers the seller's turn in the browser) and the NVIDIA speech path are built and their pieces pass, but the full live shift in the browser is not yet tested. The detailed state and next steps are in [`agents/plans/roadmap.md`](agents/plans/roadmap.md) under "Current state".

## Result: brain OFF vs ON

`cd backend && SIM_FAST=1 python eval.py` (about 20 s, offline). The brain trains on 20 simulated sellers and is tested on 10 sellers it has never seen. `EVAL_SEED=2` runs a second split.

| Held-out sellers | Brain OFF | Brain ON |
|---|---|---|
| Saved vs asking price (seed 1 / seed 2) | 13.7% / 15.4% | **16.4% / 19.9%** |
| Share of the possible discount captured (seed 1 / seed 2) | 100.6% / 93.6% | **119.6% / 122.7%** |
| Rounds to close (seed 1 / seed 2) | 3.9 / 3.4 | **2.9 / 2.4** |
| Deals closed, scam blocked (seed 1 / seed 2) | 10/10, 1/1 / 10/10, 1/1 | 10/10, 1/1 / 10/10, 1/1 |

Seed 1 is stored in `backend/data/eval_result.json`. Seed 2 was re-run on 2026-10-17 with `EVAL_SEED=2`. Two seeds is not yet a spread; more seeds are on the roadmap.

Each simulated seller type has a hidden weak tactic. The mapping exists only in `backend/sim.py`; agents never see it. The brain-ON agents learn it from playbook stats stored in the brain.

## What it does

- **Source:** You.com Search finds real listings near the dealer, and Craigslist listings are pulled as well. Nemotron Nano parses year, miles, price and VIN from page text.
- **Appraise:** You.com Research (`lite`) returns a fair-value range with citations. These become `market` facts in the brain, with source URLs. A VIN check looks for web-reported flags.
- **Negotiate:** the buyer agent identifies the seller type, recalls that seller and the playbook, picks a tactic, and haggles within the dealer's max. Offers are clamped in code, not by the model. Off-platform payment links are blocked and the seller is red-flagged.
- **Owner approval:** every buy waits in the dashboard for **Approve / Reject**. Rejection reasons become dealer preferences that later scouting respects.
- **List and sell:** the seller agent writes the listing, then negotiates with simulated buyers above the dealer's floor and minimum profit.
- **Live seller (optional):** tick "I answer as the first seller" on the Shift tab. The first deal's seller is a person: the agent's lines are spoken (Magpie), and the seller's answer is recorded in the browser (Parakeet) or typed. The turn banner shows whose turn it is. No answer within 120 s and the simulated seller answers that round. No real person is contacted.
- **Concierge:** an OpenClaw agent in a NemoClaw sandbox drives the dealer API ("start a shift for Tacomas", "what happened overnight?").

## Pipeline

```
Dealer setup (dashboard) -> brain: dealer facts (budget, per-car limit, min profit, preferences)
        |
POST /demo/start (alias /shift/start) -> swarm.py: a simulated 8-hour shop day, up to 4 deals in parallel, ~5 min; clear wins auto-approve, borderline ones wait for the dealer; after-buy steps run in the background
        |
scout       You.com Search, Craigslist -> Contents -> Nano extract -> listings
appraise    You.com Research -> Nano extract {low, mid, high, issues, sources} -> brain.market
negotiate   recall(party, dealer, playbook) -> segment -> tactic -> seller (sim, or live person)
            -> brain.write(playbook counter, party facts, red flags) + MISTAKES.md on a miss
approve     state=awaiting_approval -> dashboard Approve / Reject -> POST /deals/{id}/approve
logistics, storefront, sell   transport quote -> listing copy -> sim buyer -> sold, margin -> brain.write
librarian   every 3 deals: compacts the brain, distils lessons
        |
GET /events, /deals, /brain, /eval -> React dashboard
```

**Read-before / write-after.** Each agent loads its own `backend/skills/<agent>/SKILL.md` plus its top `MISTAKES.md` lines, then `brain.recall()`s company facts within a character budget. It works, then `brain.write()`s facts and counters.

**The brain** (`backend/brain.py`) is an append-only event log with a pure reducer, so replay order doesn't change the result. It has four scopes (dealer, party, market, playbook), capped observations, a TTL on market prices, explicit conflict records, and cold/warm snapshots for the demo. Long-term memory search uses an embedded vector store (`vector_memory.py`).

## Sponsors: how each is used

| Sponsor | Where | How |
|---|---|---|
| **Crusoe Managed Inference** | `backend/llm.py` | Every LLM call goes through the OpenAI-compatible API, with per-model RPM throttling, 429/503 backoff and a mock fallback. |
| **NVIDIA Nemotron** | `backend/agent_tiers.py`, `backend/llm.py` | 3 Super: owner lead, buyer agent (negotiation, appraisal), seller agent. 3 Nano: listing extraction, classification. 3.5 Lightning: simulated sellers and buyers, librarian. Nano Omni: photo checks (stretch). |
| **NVIDIA NemoClaw / OpenShell** | `nemoclaw/` | The `dealer` sandbox (OpenClaw on Crusoe Nemotron 3 Super) runs on a DigitalOcean droplet. Egress policy allows only You.com and the dealer API; the scam payment domain is blocked and shows in `openshell term`. The `dealer-concierge` skill drives the API. |
| **You.com** | `backend/youcom.py` | Search (listings), Contents (listing pages), Research (cited valuations). Disk cache plus `DEMO_MODE=1` for offline runs; it never raises. |
| **NVIDIA Speech and embeddings** | `backend/voice.py`, `backend/vector_memory.py` | Parakeet ASR (`parakeet-tdt-0_6b-v2`) and Magpie TTS (`magpie-tts-multilingual`) on NVCF for the live seller. Embeddings from `nvidia/nemotron-3-embed-1b` for memory search. Without `NVIDIA_API_KEY`, the seller answers by text and search uses a local hash embedding. |

## Run

```bash
cp .env.example backend/.env       # fill CRUSOE_API_KEY, YDC_API_KEY, NVIDIA_API_KEY (optional)
cd backend && pip install -r requirements.txt
cd backend && python crusoe_check.py     # verify Crusoe key and model tiers
cd backend && python nvidia_check.py     # optional: verify NVIDIA key, speech and embeddings
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm install && npm run dev                  # dashboard
```

- **NVIDIA key:** build.nvidia.com, sign in, profile > API Keys > Generate. Put it in `backend/.env` as `NVIDIA_API_KEY=nvapi-...`. Never commit it.
- **No keys:** mock mode, the full UI still works.
- **`DEMO_MODE=1`:** You.com answers come from `backend/data/cache` (real listings, pre-warmed), so no network is needed.
- **Live seller:** Shift tab, tick "I answer as the first seller", then start the shift. The mic needs `localhost` or HTTPS.
- **Eval:** `cd backend && SIM_FAST=1 python eval.py`. Set `EVAL_SEED=2` for the second split. Stop any running shift first.
- **Reset the demo:** `cd backend && python reset_demo.py [cold|warm]`.
- **NemoClaw sandbox:** follow `nemoclaw/SETUP.md`.

## Status and known gaps

Tested: brain order-independence and memory tiers (`test_brain.py`, `test_memory_tiers.py`), the eval, and the NVIDIA speech round trip (`nvidia_check.py`).

Not yet tested:
- The live shift in the browser: mic recording, the turn banner, agent audio playback, and the typed fallback.
- Real speech inside a live negotiation (only the standalone round trip has run).
- Mic access on a non-localhost origin (needs HTTPS).
- The dashboard served from the droplet (the demo currently runs from a laptop against the droplet API or a local backend).
- Degraded mode after repeated LLM failures.

## Safety

- No real person is contacted. Real listings are read-only, and every seller and buyer is simulated. The live seller is the only human, and that is someone at the dealer's own desk playing the seller in a demo.
- Every outbound message carries an AI-assistant disclosure.
- No buy happens without the owner's Approve.
- Offers above `max_buy` and sales below the floor are blocked in code.
- Keys stay in `backend/.env` (never committed) or the OpenShell gateway, outside the sandbox.

## Layout

```
backend/   FastAPI: main.py (routes), swarm.py (shift), ops.py (logistics, storefront), agents.py (negotiation),
           live.py (live seller), brain.py, memory_layer.py, vector_memory.py, librarian.py,
           sim.py, eval.py, youcom.py, craigslist.py, llm.py, voice.py, skills.py,
           nvidia_check.py, crusoe_check.py, reset_demo.py
backend/skills/  SKILL.md + MISTAKES.md per agent
frontend/  Vite + React + TypeScript dashboard (Shift, Buying, Inventory, Selling, Insights, Setup)
nemoclaw/  sandbox runbook, egress presets, concierge skill
docs/project-idea.md   full pitch; agents/plans/roadmap.md   build plan and current state
```
