# Carly: a local agent team that runs a used-car dealership's buying and selling, and gets sharper with every deal

> **Track: Problem Statement 2, Shared Brain.** We pitch one track only.
> Every agent reads one shared memory before it works and writes to it after. We prove the memory makes the team measurably better at negotiating, sourcing and selling.

---

## 1. One-liner

A **large used-car dealership** runs **Carly** as a local swarm. Two teams share one brain:

- **Buy swarm** — continuously watches Kelley Blue Book comps, Facebook Marketplace, Craigslist, Autotrader, auctions and classifieds (via You.com), values cars, talks to people who want to sell, and only buys after the GM approves.
- **Sell swarm** — keeps a dealer profile / listing pack on every channel we demo, talks to people who want to buy, asks qualifying questions, and closes above floor.

Each conversation and each outcome goes into the **shared brain**, so the next scout, the next counter, and the next buyer Q&A are sharper.

**Pitch line:** *"Your floor never sleeps. It hunts inventory, talks to sellers and buyers, and never forgets what worked."*

---

## 2. Why Shared Brain (and not the other two tracks)

| Reason | Detail |
|---|---|
| The product depends on memory | A dealer's edge is what they know: which sellers fold, which trims sell in a week, what this owner refuses to stock. Without memory, the agents are a search bar plus a chatbot. |
| Several agents share one memory | Scout, appraiser, negotiator, logistics, listing and closer agents all touch the same cars, people and prices. A shared brain is necessary here, not an add-on. |
| The gain is easy to measure on stage | The same held-out deals, run with the brain off and then on, give a before/after number (surplus captured, close rate, margin). Judges see a chart, not a claim. |
| The other tracks would dilute the pitch | The existing `loop.py` verifier (Done Means Done) and any prompt rewriting (Version N+1) are **not pitched**. Learned negotiation tactics are stored as brain records with win/loss counters. They are memory, not prompt rewriting. |

What the track asks for, and how we answer it:

| Track requirement | Our answer |
|---|---|
| Every agent reads before work | First call: own `SKILL.md` + top mistakes, then `brain.recall(task)`. Recalled chips + skill chips show in the UI. |
| Every agent updates after work | Last calls: `brain.write(...)` and, on a miss, one line in that agent's `MISTAKES.md`. |
| Lean | Hard caps per scope, a TTL on market prices, dedup by key, a character budget on recall (~1.5k chars), and a librarian agent that compacts the log. |
| Conflict-free | Writes are events and never overwrites. A deterministic reducer merges them: counters add, observations aggregate to a median, facts resolve by confidence then time. Contradictions are flagged and never silently dropped. |
| Measurable quality gain | Brain OFF vs brain ON on held-out scenarios. Section 8 has the details. |

---

## 3. Problem

A high-volume lot still runs buy and sell as human inboxes:

- Staff scroll Facebook Marketplace, Craigslist, Autotrader, auctions and KBB comps all day, then lose the thread overnight.
- Buyers text "is this still available?" and "what's your best price?" — answers are slow, inconsistent, and never written into a customer profile.
- Sellers of trade-ins and private cars get one-off haggling. Nobody remembers that this wholesaler always folds after the second comp.
- Listings are copy-pasted per site. Price and photos drift. The lot has no single "profile" of what it stocks and what it will pay.
- What the desk learns lives in one closer's head. Night shift starts from zero.

The swarm exists so **search, talk, qualify, list, and remember** keep running after the desk goes home.

---

## 4. Solution

One FastAPI swarm, **two pipelines**, one brain:

```
BUY:   WATCH -> APPRAISE -> TALK TO SELLER -> [GM APPROVES] -> BUY -> SHIP
SELL:  LIST ON CHANNELS -> TALK TO BUYER (qualify) -> CLOSE -> [GM APPROVES IF BELOW FLOOR]
              \__________ every step reads the SHARED BRAIN first, writes to it after __________/
```

- **Local / always-on / sandboxed:** same as before (NemoClaw + OpenShell). GM walks away; Concierge pings for YES/NO only.
- **Continuous watch:** Scout does not run once. A shift loop re-queries sources on a timer (demo: every N seconds with cache). New listings that match the lot profile become deals.
- **Talk to people:** Negotiator (buy-side) and Intake + Closer (sell-side) run multi-turn chats. They ask questions, do not dump a form.
- **Marketplace presence:** Merchandiser maintains one **listing pack** (title, price, photos, VIN, disclosure) and "publishes" it to each channel card: dealer storefront, Facebook Marketplace-style, Craigslist-style, Autotrader-style. Same brain record, per-channel copy.

### Persona (for the demo)

**Valley Motors, Stockton CA.** High-volume independent group, ~200-car lot + wholesale. Buys trucks, Japanese SUVs, and clean commuter cars, $8k to $45k, under 120k miles, **clean title only**. Targets **12–15% gross** retail, never pay over **92% of KBB/retail comps**. GM: "No rebuilt, no out-of-state titles without a desk check, no off-platform payment links."

### What we search (and how — live vs simulated)

| Source | Why | Live in the hackathon | Never in the hackathon |
|---|---|---|---|
| **Kelley Blue Book / book values** | Buy max and list price | You.com **Research** cited valuation ("KBB / typical listing range") written into `market` obs | Scraping kbb.com, unofficial KBB APIs |
| **Facebook Marketplace** | Private-party inventory and retail demand | You.com **Search + Contents** for public Marketplace-indexed listings | Logging into Facebook, creating a real Page, messaging real sellers |
| **Craigslist / Autotrader / Cars.com / auctions** | Same | You.com Search + Contents | Scraping sites that block bots |
| **Dealer storefront** | Our sell-side profile | Our own React page + simulated channel cards | Real paid classifieds accounts |

**Hard product rule:** we **never message a real person** and we **never create real third-party marketplace accounts**. Chats are a simulator wired to real (or cached) listing text. Channel "profiles" are listing packs we own. That is still the swarm judges see: watch → value → talk → list → sell, with memory.

### Buyer / seller questions the agents actually ask

**To a seller (buy swarm):** year/trim, miles, title status, accidents, how many keys, payoff, why selling, timeline, lowest number if we pick up this week.

**To a buyer (sell swarm):** budget, must-have (cab, 4x4, seats), timeline, trade-in, financing vs cash, zip for delivery. Answers become a `party` profile (`buyer:{id}`) so the next message is not "is this still available?" on a loop.

---

## 5. Agentic company (org chart)

This is a **company of agents**, not a flat list. One process, named bosses, platform workers.

```
Owner Agent                          (GM: goals, YES/NO, who works which deal)
│
├── Buyer Agent                      (acquisition desk)
│   ├── FB Marketplace buyer         (watch + talk on FB-indexed listings)
│   ├── Craigslist buyer
│   ├── Autotrader / auction buyer
│   ├── KBB / book buyer             (You.com Research comps → max_buy)
│   └── Logistics                    (simulated buy + ship)
│
└── Seller Agent                     (retail desk)
    ├── Storefront seller            (our lot page)
    ├── FB Marketplace seller        (FB-style listing pack + buyer chat)
    ├── Craigslist seller
    └── Autotrader seller
```

**Owner Agent** does not scrape or haggle. It assigns work, enforces policy, and is the only one that can approve a buy or a below-floor sell. It talks to the human GM through the dashboard, where every buy waits for Approve / Reject.

**Buyer Agent** owns inbound inventory. It dispatches the platform buyer that matches the listing source. It rolls up offers and asks Owner for YES.

**Seller Agent** owns outbound inventory. It dispatches the platform seller that matches the channel the customer came from. Intake questions + close happen *on that platform agent*, so Facebook learnings stay on the Facebook seller.

Same FastAPI process. "Several agents" = several functions + a queue, not several services.

| Agent | Reports to | Platform | Job |
|---|---|---|---|
| **Owner Agent** | human GM | none | Brief, assign, approve, escalate conflicts |
| **Buyer Agent** | Owner | all buy sources | Route listing → platform buyer, clamp `max_buy`, request approval |
| **FB / CL / Autotrader buyer** | Buyer Agent | that site | Watch + multi-turn seller chat on that site's listings only |
| **KBB / book buyer** | Buyer Agent | KBB-style comps | Cited valuation, issues, `max_buy` |
| **Logistics** | Buyer Agent | carriers | Simulated escrow + transport |
| **Seller Agent** | Owner | all sell channels | One listing pack → clone per channel, route buyer chats |
| **Storefront / FB / CL / Autotrader seller** | Seller Agent | that channel | Qualify buyer, ask questions, close above floor |
| **Librarian** | Owner | brain + skills | Compact events, promote repeated mistakes into skills |

### 5.1 Per-agent skill + mistake files

**In code:** `backend/skills.py`. `skills.load(agent, voice=...)` returns the agent's own `SKILL.md`, the shared playbook, the voice-calls skill when voice is on, and its top 5 `MISTAKES.md` lines. `skills.record_mistake(agent, line)` prepends a dated line and bumps `hits` on a repeat. The negotiator (`buyer/outreach`) already does both: it emits a `skill` event and shows its mistakes as Recalled chips, and a scam link writes a mistake line.

Every agent has **its own skill folder**. Company facts stay in the shared brain. Craft and failures stay on the worker that made them, so Facebook's "don't open off-platform links" does not bloat the Craigslist seller prompt.

```
backend/skills/
  owner/SKILL.md              owner/MISTAKES.md
  buyer/SKILL.md              buyer/MISTAKES.md
  buyer.fb/SKILL.md           buyer.fb/MISTAKES.md
  buyer.craigslist/SKILL.md   buyer.craigslist/MISTAKES.md
  buyer.autotrader/SKILL.md   buyer.autotrader/MISTAKES.md
  buyer.kbb/SKILL.md          buyer.kbb/MISTAKES.md
  seller/SKILL.md             seller/MISTAKES.md
  seller.fb/SKILL.md          seller.fb/MISTAKES.md
  ...
```

| File | What goes in | Cap (lean) |
|---|---|---|
| `SKILL.md` | How *this* agent works this platform: search recipe, talk script, disclosure, what to write to the brain | ~800 chars. Owner/Librarian may rewrite only if a mistake repeats. |
| `MISTAKES.md` | Dated bullets: what went wrong, what to do instead, `hits` count | 20 bullets. Newest + highest hits. Dedup by normalised text. |

**Read-before / write-after (every worker):**

1. Read own `SKILL.md` + top 5 `MISTAKES.md` lines (hard char cap).
2. `brain.recall(...)` for company facts only (dealer policy, this party, this segment) — **not** other agents' skills.
3. Do the work.
4. `brain.write(...)` for facts/counters.
5. If the outcome was a miss (bad offer, scam link, rejected by Owner, buyer ghosted after a dumb question): **append one mistake line**. If it was a repeat win: optionally one line into `SKILL.md` playbook, still under the cap.

Owner Agent can read **summaries** of child mistake files (Librarian packs them), never the raw union of every skill — that would blow the token budget.

This is still **Shared Brain**, not Version N+1. Skills are memory the agent owns. We do not pitch "we rewrote the system prompt." We show the mistake file grow on screen.

**Demo beat:** FB buyer clicks a scam payment link → OpenShell blocks → `buyer.fb/MISTAKES.md` gets `off-platform payment URL; flag party; never fetch`. Next FB listing with a similar link: Recalled chip shows that mistake. Craigslist buyer never sees it.

**Hard rules enforced in code, not by prompts:**
- An offer is never above `dealer.max_buy` for that car. It is clamped before sending.
- A sell is never below `dealer.floor` without an `approval_request`.
- Buy and sell commitments create an `approval_request`. Nothing executes until the GM approves.
- Every outbound message to a seller or buyer carries an AI-assistant disclosure line.
- Watcher never follows off-allowlist links (OpenShell). Scam payment URLs are red-flagged on `party`.

---

## 6. The Shared Brain (the core of the pitch)

### 6.1 Four scopes

| Scope | Holds | Example records |
|---|---|---|
| `dealer` | Owner preferences, inventory, sales history, margin targets, learned likes and dislikes | `{"attr":"max_mileage","value":110000}`, `note: "Joe rejected 3 cars with >2 owners, avoid"` |
| `party` | One record set per seller or buyer: what they said, their constraints, their reaction to tactics, red flags | `seller:craig-tacoma`, `signal: "moving next week"`, `flag: "sent off-platform payment link"` |
| `market` | Price comps, days-to-sell, shipping costs, auction fees. Each one cites a URL and has a timestamp. | `obs: tacoma-2019-trd / private_value = 24100 (src: ...)` |
| `playbook` | Negotiation and listing tactics with win/try counters per segment | `counter: tactic=fast_cash_pickup, segment=motivated_private, wins=7, tries=9` |

### 6.2 Read-before / write-after protocol

```python
ctx = brain.recall(scopes=["dealer", "party", "playbook"],
                   keys=[f"seller:{seller_id}", segment],
                   budget_chars=1500)                  # lean: hard budget
reply = await negotiator(listing, history, ctx)        # agent works
brain.write(agent="negotiator", scope="party", key=f"seller:{seller_id}",
            kind="note", value=summary, source=f"chat:{deal_id}", confidence=0.7)
brain.write(agent="negotiator", scope="playbook", key=f"{tactic}|{segment}",
            kind="counter", value={"tries": 1, "wins": int(closed)})
```

The UI shows **"Recalled:"** chips under every agent action, so the audience can see the memory being used.

### 6.3 Conflict-free by design

- **Storage:** one append-only `events.jsonl`. Agents only append, under one asyncio lock in one process.
- **Views:** produced by a pure reducer over the events. Same events give the same brain, whatever the order the agents wrote in.
- **Merge rules by kind:**
  - `counter`: values are summed. Parallel writes commute, so they never conflict.
  - `obs` (numeric observation): kept as a capped list, read as a median. Entries older than the TTL drop out.
  - `fact`: highest confidence wins, then newest. If two high-confidence facts disagree, the reducer emits a **conflict** record.
  - `note`: deduped by normalised text and capped per key. The librarian folds old notes into one summary.
- **Conflicts are visible:** the Brain tab lists them, for example *"Appraiser says retail $26.1k (KBB-cited), Merchandiser observed sale at $23.4k. Flagged."* The librarian resolves easy ones. The rest go to the owner.

### 6.4 Lean by design

- Caps: 50 notes per party, 200 market observations per segment, 30 dealer notes.
- Market observations expire after 30 days.
- Recall budget: about 1,500 characters per agent call, ranked by key match, then confidence, then recency.
- Librarian compaction runs every N deals. Brain size is shown in the UI before and after compaction.

### 6.5 Self-improvement through the brain **and** per-agent skills

- **Playbook (company):** Buyer/Seller leads pick tactics from `playbook` counters. Brain OFF → default tactic. Brain ON → best win rate with a little exploration.
- **Mistake skills (per platform):** a miss writes to that agent's `MISTAKES.md`. Repeats increment `hits`. Librarian promotes a high-hit mistake into that agent's `SKILL.md` and may copy a *dealer-policy* fact into the company brain (example: "never follow off-platform pay links" as a `dealer` note). Platform-specific craft stays in the skill file.
- **Preference learning:** Owner YES/NO updates `dealer` notes. Watchers on every buy platform tighten.
- **Counterparty memory:** `party` records are company-wide. The FB buyer and the FB seller both see that this person sent a scam link.

---

## 7. NVIDIA, NemoClaw, OpenShell, Crusoe and You.com: where each one shows up on screen

| Sponsor tech | What we use it for | Visible demo moment |
|---|---|---|
| **NVIDIA NemoClaw** | Installs and runs the dealer's always-on agent on the dealer's own machine (`nemoclaw onboard`). An OpenClaw concierge agent lives in the sandbox and drives the dealer API (start shift, briefing, approvals) on request. | Terminal: `nemoclaw list` shows the `dealer` sandbox running, and `nemoclaw dealer agent` answers "what happened overnight?" from the API. Owner approvals happen in the dashboard. |
| **NVIDIA OpenShell** | Sandbox with a YAML network policy. Egress is allowed only to Crusoe inference, You.com and the dealer storefront. Everything else is blocked and surfaces for operator approval. Inference credentials stay in the OpenShell gateway, outside the sandbox. | **Scam moment:** a simulated seller sends a "verify payment" link to an unknown domain. The agent tries to open it, OpenShell blocks it, and the request shows up for operator review. The brain writes a red flag on that seller. |
| **NVIDIA Nemotron** (Nemotron 3 / 3.5 family) | **Super 120B** for negotiation and appraisal reasoning (Ultra 550B if `/v1/models` shows it for our project). **3.5 Lightning** for the librarian and the simulated sellers and buyers. **Nano 30B** for extraction and classification. **Nano Omni** for listing-photo condition checks (image input confirmed; stretch). Optional local Nemotron for private dealer data (stretch). Roles are spread across models on purpose, because Crusoe rate limits are per model. | A model badge on each agent action shows which Nemotron handled it. |
| **Crusoe Managed Inference** | Hosts every Nemotron call through an OpenAI-compatible API at `https://api.inference.crusoecloud.com/v1` (`backend/llm.py`). | Latency and token counter in the footer. A burst of parallel negotiations shows throughput. |
| **NVIDIA Speech (Parakeet + Magpie)** | Voice mode for the buyer and seller agents (`backend/voice.py`). Parakeet transcribes the counterparty, and Magpie speaks the agent's line. Once a seller is interested, the agent asks for a callback number and logs a masked call request. No real call is placed from the hackathon build. | Deal drawer: a play button on agent messages, and a "callback set +1******1234" event. |
| **You.com Search API** | Scout finds real, current listings (`POST ydc-index.io/v1/search`). | Live feed of real listings with their source sites. |
| **You.com Contents API** | Pulls the full listing page as Markdown for structured extraction (`POST ydc-index.io/v1/contents`). | "Parsed listing" card: year, trim, miles, price, VIN if present. |
| **You.com Research API** | Appraiser gets a cited valuation and common-issues report (`POST api.you.com/v1/research`). | Valuation card with clickable citations. These citations feed `market` brain records. |

---

## 8. Measurable quality gain (the number we show)

**Environment:** a deterministic simulator of sellers and buyers.
- Each simulated seller has a hidden `ask`, a hidden `floor` and a hidden `persona` (motivated, price-anchored, haggler, wholesaler-repeat, scammer). Each persona responds better to certain tactics. Concessions follow a formula, so outcomes are reproducible. The LLM only writes the wording.
- The simulated owner has hidden true preferences and approves or rejects candidates.
- Real listings from You.com are paired with simulated sellers. **We never message real people.**

**Protocol:**
1. 20 training scenarios. The brain learns from them.
2. 10 **held-out** scenarios: different cars, different sellers, the same kinds of persona.
3. Run the held-out set twice: **brain OFF** (empty brain) and **brain ON** (the brain after training). Same seeds, same models.

**Metrics (chart in the Eval tab):**

| Metric | Definition |
|---|---|
| Surplus captured (buy) | `(ask - paid) / (ask - floor)`, averaged. **This is the headline number.** |
| Close rate | Deals closed at or under the dealer max, divided by deals attempted |
| Rounds to close | Fewer is better |
| Owner approval rate | Approved candidates divided by proposed candidates |
| Sell margin (stretch) | `(sale - cost) / cost` on simulated buyers |

We will present only the numbers we actually measure. If the gain is small, we say so and show where it comes from.

---

## 9. Architecture

```
                 Owner's browser (React dashboard: approve / reject)
                          |                                     |
  +----------- Dealer's machine ---------------------------------------------------+
  |  NemoClaw  ->  OpenShell gateway (holds Crusoe + You.com keys, enforces policy)  |
  |                 |                                                                |
  |   +------------ OpenShell sandbox "dealer" (network policy: allowlist only) ---+ |
  |   |  OpenClaw Concierge  --skill-->  Dealer API (FastAPI)                      | |
  |   |                                     |-- swarm.py  (owner → buyer/seller leads) |
  |   |                                     |-- agents.py (platform workers)       | |
  |   |                                     |-- skills/   (SKILL.md + MISTAKES.md) | |
  |   |                                     |-- brain.py  (events.jsonl -> views)  | |
  |   |                                     |-- sim.py    (sellers / buyers / owner)| |
  |   |                                     |-- youcom.py (search/contents/research + cache)
  |   |                                     '-- llm.py    (Nemotron tiers)         | |
  |   +----------------------------------------------------------------------------+ |
  +-----------------|---------------------------------|------------------------------+
                    v                                 v
        Crusoe Managed Inference (Nemotron)    You.com APIs (ydc-index.io, api.you.com)
                    (anything else: BLOCKED by OpenShell)
```

**Plan A:** the backend runs inside the sandbox, and inference goes through the OpenShell-managed route, so no keys sit in the sandbox.
**Plan B (fallback):** the backend runs on the host, and only the OpenClaw concierge is sandboxed. The scam-link block is then shown on the concierge, which still demonstrates a real OpenShell block. The roadmap explains when to switch.

---

## 10. Demo script (3 minutes)

| Time | Beat | What the audience sees |
|---|---|---|
| 0:00 | **Hook** | "Joe runs a 40-car lot alone. Last night his agents bought him a truck." Phone shows the overnight briefing. |
| 0:20 | **Local and sandboxed** | Terminal: `nemoclaw list` shows the `dealer` sandbox. One sentence: runs on Joe's machine, Nemotron on Crusoe, keys held by OpenShell. |
| 0:35 | **Start a shift** | Dashboard: Joe's profile comes from the brain. Click **Start shift**. |
| 0:50 | **Live sourcing** | Watcher feed ticks: Facebook Marketplace / CL / Autotrader hits via You.com. Appraiser card shows a **cited** KBB-style You.com Research valuation and a clamped `max_buy`. |
| 1:15 | **Buy-side talk with memory** | Owner assigned the deal to **Buyer Agent → FB buyer**. Split view: seller chat + Recalled chips + that agent's `MISTAKES.md` line. Offer lands under `max_buy`. |
| 1:45 | **Scam blocked** | Another seller sends a "payment verification" link. The agent tries to open it and **OpenShell blocks it**. The block shows in the operator view, and a red flag appears on that seller in the Brain tab. |
| 2:05 | **Owner approves** | Dashboard: "Approve $17,900?" The owner clicks Approve. Pipeline card moves to Bought, then In transit, with a shipping quote from You.com search. |
| 2:20 | **Sell side** | Merchandiser clones one listing pack onto storefront + FB/CL-style channel cards. Intake asks the buyer budget/needs; Closer sells above floor using `buyer:{id}` memory. |
| 2:35 | **The proof** | Eval tab: brain OFF vs ON on 10 held-out deals. Headline: surplus captured X% vs Y% (measured live earlier). Brain tab: lessons learned, conflicts flagged, size kept lean. |
| 2:55 | **Close** | "A dealership's memory, run by agents, on the dealer's own machine." |

**Backup:** a recorded video of the full run, plus a demo mode with cached You.com responses and frozen brain snapshots (`cold.json`, `warm.json`).

---

## 11. Safety and trust (say this out loud. Judges ask.)

- **No real money and no real messages in the demo.** Purchases, escrow and transport are simulated. Real listings are read-only.
- **Human approval for every commitment.** The system enforces it in code, not in the prompt.
- **Prompt injection from counterparties is expected.** Seller messages are untrusted data. Any link-following goes through a tool that OpenShell polices.
- **AI disclosure** in every outbound message.
- **Least privilege:** egress allowlist, credentials outside the sandbox, a local data store.

---

## 12. Scope

**Goals**
- One end-to-end deal (source, appraise, negotiate, approve, buy, ship, list, sell) running live.
- Shared brain with all four scopes, visible recall, visible conflict handling, visible lean caps.
- A real before/after number from held-out evaluation.
- Real, visible use of NemoClaw, OpenShell, Nemotron on Crusoe, and You.com Search, Contents and Research.

**Non-goals**
- Real purchases, real payments, real contact with sellers or buyers, title and DMV paperwork.
- Real Facebook / Craigslist / Autotrader accounts, logins, or posts. Channel "profiles" are our listing packs on simulated cards plus our storefront.
- Scraping KBB, Facebook, or any site that blocks bots. If You.com doesn't return it, we cache or skip.
- Multi-dealer or multi-tenant support, auth, a database.
- Vector DB or embeddings. Key and tag recall is enough and easier to explain.

**Anti-goals (a failure even if it "works")**
- Memory that can't be shown helping. A brain judges can't see is wasted.
- A claimed improvement with no measured number.
- An agent that can spend money or contact a real person without approval.
- A blank screen or stack trace on stage.

---

## 13. Risks and fallbacks

| Risk | Likelihood | Fallback |
|---|---|---|
| NemoClaw is alpha and Linux-first. Our laptops run Windows. | **High** | Start it first on a Linux box or WSL2 + Docker. Timebox: Plan A by T+2:00, else Plan B (concierge-only sandbox). Last resort: show the policy file plus a recorded block clip. |
| Exact Crusoe model IDs differ from the docs | Medium | Check `GET /v1/models` at T+0. Model names live in `.env`, never hard-coded. |
| Crusoe rate limits: **30 RPM per model** without a payment method (600 with one) | **High** for a swarm plus eval | Add a payment method at T+0 if possible. Spread roles across models (limits are per model). Client-side throttle on the `x-ratelimit-remaining-*` headers, with jittered backoff on 429/503. |
| Reasoning models return empty `content` when `max_tokens` is too small | Medium | `max_tokens` ≥ 1024 on reasoning calls. `enable_thinking: false` on fast extraction calls. Check `finish_reason`. |
| You.com Research latency (seconds to a minute) | Medium | `research_effort: "lite"` live, results cached to disk, demo mode replays the cache. |
| Search returns few usable listings | Medium | Pre-run queries and cache them. Seed 5 real listings as a guaranteed fallback. |
| Eval shows a small or noisy gain | Medium | Deterministic simulator, fixed seeds, more held-out scenarios. Report honestly. |
| LLM returns broken JSON | High | `chat_json` retries once, then a safe default. Offers are always clamped in code. |

---

## 14. Verify at T+0 (assumptions to check before building on them)

1. NemoClaw installs on our host (`nemoclaw host probe`) and `nemoclaw onboard` accepts a **compatible OpenAI endpoint** (Crusoe base URL, key and Nemotron model).
2. How to add our own network policy entries (`nemoclaw <name> policy list` / `policy add`) and where blocked requests surface for approval (`openshell term` or the dashboard).
3. Whether code inside the sandbox can call OpenShell's managed inference route (`inference.local`) so our backend never holds a key.
4. Crusoe base URL is `https://api.inference.crusoecloud.com/v1`. **Confirmed on our project 2026-10-17** (`cd backend && python crusoe_check.py`): Super `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B`, Lightning `nvidia/Nemotron-3.5-Lightning-30B-A3B`, Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, Nano Omni `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`. Ultra is **not** enabled. Also available: `nvidia/NVIDIA-Nemotron-3.5-Super-VL` (120B multimodal, tool calling), an upgrade option for the vision tier. Source of truth: `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md`.
5. You.com key works on all three endpoints (`X-API-Key` header) and the account has credits.
6. Messaging channel: decided, none. Owner approvals live in the dashboard.

---

## 15. References

- Team Crusoe skill (endpoint, model IDs, rate limits, reasoning toggles): `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md`
- Build roadmap: `agents/plans/roadmap.md`
- NemoClaw overview (OpenClaw): https://docs.nvidia.com/nemoclaw/user-guide/openclaw/about/overview.md
- NemoClaw command reference: https://docs.nvidia.com/nemoclaw/user-guide/openclaw/reference/commands
- Crusoe: Nemotron 3 Ultra on Crusoe Managed Inference: https://www.crusoe.ai/resources/blog/nvidia-nemotron-3-ultra-langchain-deep-agents-on-crusoe-managed-inference
- Crusoe Managed Inference docs: https://docs.crusoecloud.com/managed-inference/overview
- You.com API quickstart: https://you.com/docs/quickstart
