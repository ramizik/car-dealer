# Dealer: an AI agent team for used-car dealers, with a shared brain

A team of Nemotron agents finds real used-car listings, appraises them with cited sources, negotiates with sellers, gets the owner's approval, then lists and sells the car. Every agent reads a **shared brain** before it works and writes to it after, so the team gets better with every deal.

**Track:** Shared Brain.

## Result: brain OFF vs ON

The brain trains on 20 simulated sellers and is tested on 10 sellers it has never seen.

| Held-out sellers | Brain OFF | Brain ON |
|---|---|---|
| Saved vs asking price | 13.7% / 15.4% | **16.4% / 19.9%** |
| Share of possible discount captured | 100.6% / 93.6% | **119.6% / 122.7%** |
| Rounds to close | 3.9 / 3.4 | **2.9 / 2.4** |
| Deals closed, scam blocked | 10/10, 1/1 | 10/10, 1/1 |

Two random splits (seed 1 / seed 2). Each seller type has a hidden weak tactic that agents never see; with the brain on, they learn it from shared playbook stats.

## Pipeline

```
scout       You.com Search + Craigslist -> Nemotron Nano extracts year, miles, price, VIN
appraise    You.com Research -> cited fair-value range -> brain (market facts)
negotiate   recall seller + playbook from brain -> pick tactic -> haggle within dealer's max
approve     clear wins go through; borderline deals wait for the owner (Buy / Decline)
sell        transport quote -> listing copy -> negotiate with buyers above the floor
librarian   every few deals: compacts the brain and distils lessons
```

**Read before, write after.** Each agent loads its skill file and past mistakes, recalls relevant brain facts, works, then writes new facts and tactic stats back.

**The brain** is an append-only event log with a pure reducer, so concurrent agents never conflict. Four scopes (dealer, party, market, playbook), capped observations, expiring market prices, plus vector search for long-term memory.

**One-click demo.** **Start Demo** runs a simulated shop day with several deals in parallel, buying and selling at once, plus a live seller call where a person answers by voice in the browser.

## Sponsors

| Sponsor | How we use it |
|---|---|
| **Crusoe Managed Inference** | Every LLM call goes through Crusoe's OpenAI-compatible API. |
| **NVIDIA Nemotron** | Super for the owner lead, buyer and seller agents; Nano for extraction; Lightning for simulated parties and the librarian. |
| **NVIDIA NemoClaw / OpenShell** | A concierge agent runs in a sandbox and drives the dealer API. Egress policy allows only You.com and our API, and blocks the scam payment domain. |
| **You.com** | Search finds listings, Contents reads them, Research returns cited valuations. |
| **NVIDIA Speech + embeddings** | Parakeet (speech-to-text) and Magpie (text-to-speech) for the live seller call; Nemotron embeddings for memory search. |

## Safety

- Every seller and buyer is simulated; real listings are read-only. No real person is contacted.
- Offers above the dealer's max and sales below the floor are blocked in code, not by the model.
- Off-platform payment links are blocked and the seller is red-flagged.
- No borderline buy or sale happens without the owner's yes.

## Run

```bash
cp .env.example backend/.env    # CRUSOE_API_KEY, YDC_API_KEY, NVIDIA_API_KEY (optional)
cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000
cd frontend && npm install && npm run dev
```

Without keys the app runs in mock mode. Eval: `cd backend && SIM_FAST=1 python eval.py`. NemoClaw setup: `nemoclaw/SETUP.md`.
