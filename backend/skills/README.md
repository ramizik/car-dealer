# Sub-agent skills

Each sub-agent has its own folder: `SKILL.md` (how it works) and `MISTAKES.md` (dated misses, newest first).

```
backend/skills/
  shared/sales-playbook/SKILL.md   craft shared by every talking agent (read first)
  shared/voice-calls/SKILL.md      Parakeet (speech in), Magpie (speech out), callback number capture
  buyer/kbb/                       valuation: book comps, max buy
  buyer/marketplace/               search Facebook / Craigslist / Autotrader-style listings
  buyer/outreach/                  text and talk to sellers who posted cars
  seller/listing/                  build and publish the listing pack per channel
  seller/enquiry/                  answer buyer enquiries, qualify, close above floor
  dealer/onboarding/               dealer profile, approvals, inventory, authority
  dealer/consignment-listing/      list a dealer's inventory on their chosen platforms
  dealer/auction/                  watch run lists, bid within the dealer's max, with YES
```

Read-before / write-after, every agent:

1. Read own `SKILL.md` and the top 5 lines of `MISTAKES.md`.
2. `brain.recall(task)` for company facts only (dealer policy, this party, this car).
3. Do the work. Every outbound message carries the AI-assistant disclosure line.
4. `brain.write(...)` for facts and counters.
5. On a miss, append one dated line to own `MISTAKES.md` and bump `hits` if it repeats.

## Model per agent

Tiers and model IDs are in `backend/llm.py`; the agent-to-tier map is `backend/agent_tiers.py`.

| Agent | Tier | Why |
|---|---|---|
| Owner lead, buyer agent (outreach, kbb), seller agent (listing, enquiry) | smart (Nemotron 3 Super) | approvals and routing need reasoning |
| buyer/kbb, buyer/outreach, seller/enquiry, dealer/auction | smart | valuation, negotiation, bid decisions |
| buyer/marketplace (listing search), dealer/onboarding, dealer/consignment-listing | fast (Nemotron 3 Nano) | high-volume extraction and cloning |
| sim/seller, sim/buyer, librarian | sim (Nemotron 3.5 Lightning) | simulated counterparties, long-running workers |
| photo checks | vision (Nemotron 3 Nano Omni) | image input |

Not yet wired: `loop.py` does not call `tier_for` yet. Model IDs in `llm.py` differ in casing from the Crusoe docs (for example `NVIDIA-Nemotron-3-Super-120B-A12B`). Confirm them against `GET /v1/models` before the demo.

Hard limits (enforced in code, not in prompts): no message to a real person from the hackathon build (simulator only), no offer above `max_buy`, no sell below `floor` without approval, no off-allowlist links.
