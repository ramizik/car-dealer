# Dealer: an AI agent team for used-car dealers, with a shared brain

A team of Nemotron agents finds real used-car listings, appraises them with cited sources, negotiates with sellers, asks the owner to approve, then lists and sells the car. Every agent reads a **shared brain** before it works and writes to it after. On sellers it has never seen, the team negotiates measurably better and faster than the same agents with the brain off.

**Track:** Shared Brain. **Sponsors used:** Crusoe Managed Inference, NVIDIA Nemotron, NVIDIA NemoClaw / OpenShell, You.com APIs, NVIDIA Speech (Parakeet, Magpie).

## Result: brain OFF vs ON

`cd backend && SIM_FAST=1 python eval.py` (about 20 s, offline). The brain trains on 20 simulated sellers and is tested on 10 sellers it has never seen.

| Held-out sellers | Brain OFF | Brain ON |
|---|---|---|
| Saved vs asking price (seed 1 / seed 2) | 13.7% / 15.4% | **16.4% / 19.9%** |
| Share of the possible discount captured | 100.6% / 93.4% | **119.6% / 122.4%** |
| Rounds to close | 3.9 / 3.3 | **2.9 / 1.8** |
| Deals closed, scam blocked | 10/10, 1/1 | 10/10, 1/1 |

Each simulated seller type has a hidden weak tactic. The mapping exists only in `backend/sim.py`; agents never see it. With the brain ON, the agents pick the right tactic for 9 of 10 held-out sellers, learning it only from playbook stats in the brain.

## What it does

- **Source:** You.com Search finds real listings near the dealer (craigslist, cars.com, TrueCar). Nemotron Nano parses year, miles, price and VIN from page text.
- **Appraise:** You.com Research (`lite`) returns a fair-value range with citations. These become `market` facts in the brain, with source URLs.
- **Negotiate:** the buyer agent identifies the seller type, recalls that seller and the playbook, picks a tactic, and haggles within the dealer's max. Offers are clamped in code, not by the model. Off-platform payment links are blocked and the seller is red-flagged.
- **Owner approval:** every buy waits in the dashboard for **Approve / Reject**. Rejection reasons become dealer preferences that later scouting respects.
- **List and sell:** the seller agent writes the listing, then negotiates with simulated buyers above the dealer's floor and minimum profit.
- **Voice (optional):** Parakeet transcribes counterparties and Magpie speaks agent lines. Agents collect a callback number from interested sellers and store it masked.
- **Concierge:** an OpenClaw agent in a NemoClaw sandbox drives the dealer API ("start a shift for Tacomas", "what happened overnight?").

## Pipeline

```
Dealer setup (dashboard) -> brain: dealer facts (budget, per-car limit, min profit, preferences)
        |
POST /shift/start -> swarm.py: 3 deals in parallel
        |
scout       You.com Search -> Contents (or search snippets) -> Nano extract -> listings
appraise    You.com Research -> Nano extract {low, mid, high, issues, sources} -> brain.market
negotiate   recall(party, dealer, playbook) -> segment -> tactic -> sim seller (Lightning)
            -> brain.write(playbook counter, party facts, red flags) + MISTAKES.md on a miss
approve     state=awaiting_approval -> dashboard Approve / Reject -> POST /deals/{id}/approve
list, sell  seller agent -> sim buyer (Lightning) -> sold, margin -> brain.write
        |
GET /events, /deals, /brain, /eval -> React dashboard (Shift, Brain, Money, Eval)
```

**Read-before / write-after.** Each agent loads its own `backend/skills/<agent>/SKILL.md` plus its top `MISTAKES.md` lines, then `brain.recall()`s company facts within a character budget. It works, then `brain.write()`s facts and counters.

**The brain** (`backend/brain.py`) is an append-only event log with a pure reducer, so replay order doesn't change the result. It has four scopes (dealer, party, market, playbook), capped observations, a TTL on market prices, explicit conflict records, and cold/warm snapshots for the demo.

## Sponsors: how each is used

| Sponsor | Where | How |
|---|---|---|
| **Crusoe Managed Inference** | `backend/llm.py` | Every LLM call goes through the OpenAI-compatible API, with per-model RPM throttling, 429/503 backoff and a mock fallback. |
| **NVIDIA Nemotron** | `backend/agent_tiers.py` | 3 Super: owner lead, buyer agent (negotiation, appraisal), seller agent. 3 Nano: listing-search subagent, extraction, classification. 3.5 Lightning: simulated sellers and buyers, librarian. Nano Omni: photo checks (stretch). |
| **NVIDIA NemoClaw / OpenShell** | `nemoclaw/` | The `dealer` sandbox (OpenClaw on Crusoe Nemotron 3 Super) runs on a DigitalOcean droplet. Egress policy allows only You.com and the dealer API; the scam payment domain is blocked and shows in `openshell term`. The `dealer-concierge` skill drives the API. |
| **You.com** | `backend/youcom.py` | Search (listings), Contents (listing pages), Research (cited valuations). Disk cache plus `DEMO_MODE=1` for offline runs; it never raises. |
| **NVIDIA Speech** | `backend/voice.py` | Parakeet ASR and Magpie TTS on NVCF for voice negotiation. Falls back to text without a key. |

## Run

```bash
cp .env.example backend/.env      # CRUSOE_API_KEY, YDC_API_KEY (optional: NVIDIA_API_KEY)
cd backend && pip install -r requirements.txt
cd backend && python crusoe_check.py                       # verify key and model tiers
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm install && npm run dev                  # dashboard
```

- **No keys:** mock mode, the full UI still works.
- **`DEMO_MODE=1`:** You.com answers come from `backend/data/cache` (real listings, pre-warmed), so no network is needed.
- **NemoClaw sandbox:** follow `nemoclaw/SETUP.md`.

## Safety

- No real person is contacted. Real listings are read-only, and every seller and buyer is simulated.
- Every outbound message carries an AI-assistant disclosure.
- No buy happens without the owner's Approve.
- Offers above `max_buy` and sales below the floor are blocked in code.
- Keys stay in `.env` (never committed) or the OpenShell gateway, outside the sandbox.

## Layout

```
backend/   FastAPI: swarm.py, agents.py, brain.py, sim.py, youcom.py, llm.py, voice.py, skills.py, eval.py
backend/skills/  SKILL.md + MISTAKES.md per agent
frontend/  Vite + React + TypeScript dashboard
nemoclaw/  sandbox runbook, egress presets, concierge skill
docs/project-idea.md   full pitch; agents/plans/roadmap.md   build plan
```
