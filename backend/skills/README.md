# Sub-agent skills

Each sub-agent has its own folder: `SKILL.md` (how it works) and `MISTAKES.md` (dated misses, newest first).

```
backend/skills/
  shared/sales-playbook/SKILL.md   craft shared by every talking agent (read first)
  buyer/kbb/                       valuation: book comps, max buy
  buyer/marketplace/               search Facebook / Craigslist / Autotrader-style listings
  buyer/outreach/                  text and talk to sellers who posted cars
  seller/listing/                  build and publish the listing pack per channel
  seller/enquiry/                  answer buyer enquiries, qualify, close above floor
```

Read-before / write-after, every agent:

1. Read own `SKILL.md` and the top 5 lines of `MISTAKES.md`.
2. `brain.recall(task)` for company facts only (dealer policy, this party, this car).
3. Do the work. Every outbound message carries the AI-assistant disclosure line.
4. `brain.write(...)` for facts and counters.
5. On a miss, append one dated line to own `MISTAKES.md` and bump `hits` if it repeats.

Hard limits (enforced in code, not in prompts): no message to a real person from the hackathon build (simulator only), no offer above `max_buy`, no sell below `floor` without approval, no off-allowlist links.
