# Dealer: a local agent team that runs a used-car dealership's buying and selling, and gets sharper with every deal

> **Track: Problem Statement 2, Shared Brain.** We pitch one track only.
> Every agent reads one shared memory before it works and writes to it after. We prove the memory makes the team measurably better at negotiating, sourcing and selling.

---

## 1. One-liner

A small used-car lot installs **Dealer** on its own machine. Overnight, a team of sandboxed agents (running under NVIDIA NemoClaw and OpenShell, powered by Nemotron on Crusoe) finds cars on public marketplaces and auctions using You.com, values them with cited research, negotiates with sellers, buys and ships the car once the owner approves by phone, then lists it on the dealer's own channels and negotiates the sale. Each conversation and each outcome goes into a **shared brain**, so tomorrow's team negotiates better than today's.

**Pitch line:** *"Your best buyer never sleeps, never forgets a seller, and never touches a website you didn't approve."*

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
| Every agent reads before work | `brain.recall(task)` is the first call in every agent function. The recalled lines appear in the UI next to each agent action. |
| Every agent updates after work | `brain.write(...)` is the last call. Each write is an append-only event with agent, source and confidence. |
| Lean | Hard caps per scope, a TTL on market prices, dedup by key, a character budget on recall (~1.5k chars), and a librarian agent that compacts the log. |
| Conflict-free | Writes are events and never overwrites. A deterministic reducer merges them: counters add, observations aggregate to a median, facts resolve by confidence then time. Contradictions are flagged and never silently dropped. |
| Measurable quality gain | Brain OFF vs brain ON on held-out scenarios. Section 8 has the details. |

---

## 3. Problem

Small independent dealers do everything by hand:

- Hours every day scrolling marketplaces, auction run lists and classifieds for cars that fit their lot.
- Valuing each car by gut feel or with a paid book tool.
- Haggling with private sellers over text, one at a time.
- Arranging transport, chasing paperwork, writing listings, answering buyer questions, haggling again.
- What they learn (which sellers are flexible, which trims move, which phrasing gets calls) lives in one person's head and disappears between deals.

Big dealer groups have buying centres and data teams. Small lots have the owner and a phone.

---

## 4. Solution

A **local, always-on agent team** that works for one dealership:

```
SOURCE  ->  APPRAISE  ->  NEGOTIATE  ->  [OWNER APPROVES]  ->  BUY  ->  SHIP  ->  LIST  ->  SELL
   \__________ every step reads the SHARED BRAIN first, writes to it after __________/
```

- **Local:** runs on the dealer's own box inside an NVIDIA NemoClaw sandbox. Dealer data stays with the dealer.
- **Always-on:** a "shift" keeps running after the dashboard closes. The owner walks away, then gets a briefing and approval requests on their phone (NemoClaw messaging channel).
- **Safe by construction:** OpenShell decides what the agents can reach. Inference keys stay outside the sandbox. No money moves without an explicit owner "yes".
- **Learns:** the brain stores what each conversation and each sale taught, and every agent uses it next time.

### Persona (for the demo)

**Joe's Auto, Stockton CA.** 40-car lot. Buys trucks and Japanese SUVs, $12k to $30k, under 110k miles, clean title only, targets 15% gross margin. Joe says "never buy rebuilt titles, never pay over 92% of retail". Joe has no time.

---

## 5. Agent team

All agents are plain async Python functions in one backend. "Swarm" means several deals move through the pipeline at once, with many agent instances in parallel, not many services.

| Agent | Job | Reads from brain | Writes to brain | Model (Crusoe unless noted) | External tools |
|---|---|---|---|---|---|
| **Concierge** | Owner-facing assistant. Takes goals, sends briefings, relays approvals. | Dealer profile, open deals | Owner preferences said in chat, approve/reject decisions | Nemotron (via NemoClaw / OpenClaw runtime) | NemoClaw messaging channel (Telegram) |
| **Scout** | Finds candidate cars on marketplaces, auctions and public listings. | Dealer profile (makes, price band, mileage cap, region), past rejections | Listing seen, source quality (which sites gave approvable cars) | Nemotron Nano (extraction) | **You.com Search API**, **You.com Contents API** |
| **Appraiser** | Values the car with cited comps, flags known issues, scores the deal. | Market comps for this segment, days-to-sell stats | Price observations with source URLs, known-issue notes | Nemotron Super/Ultra (reasoning). Nano Omni for photos (stretch) | **You.com Research API** |
| **Negotiator** | Talks to the seller and gets the lowest price at or under the dealer's max. | Counterparty memory (this seller and similar sellers), playbook stats, dealer max | Conversation summary, seller signals, tactic used and its outcome | Nemotron 3 Super (Ultra if enabled for our project) | Simulated seller channel |
| **Logistics** | Buys after approval (simulated escrow), books transport, tracks delivery. | Shipping cost observations per route, carrier notes | Quote and actual cost, delays | Nemotron Nano | **You.com Search** for carrier rates |
| **Merchandiser** | Writes the listing, sets the price, publishes it to the dealer's own channels. | "What sells" stats, comps, dealer margin target | Listing variant, list price | Nemotron Super | Dealer storefront page plus Telegram channel post (stretch) |
| **Closer** | Handles buyer inquiries and negotiates the sale upward. | Buyer memory, playbook stats (sell side), floor price | Buyer signals, tactic outcome, final sale | Nemotron Super | Simulated buyer channel |
| **Librarian** | Compacts the brain, resolves or flags conflicts, distils lessons. | Whole event log | Compacted views, conflict flags, lessons | Nemotron 3.5 Lightning (built for long-running sub-agents, 1M context) | None |

**Hard rules enforced in code, not by prompts:**
- An offer is never above `dealer.max_buy` for that car. It is clamped before sending.
- Buy and sell commitments create an `approval_request`. Nothing executes until the owner approves.
- Every outbound message to a seller or buyer carries an AI-assistant disclosure line.

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

### 6.5 Self-improvement through the brain

- **Playbook learning:** the negotiator picks a tactic for the seller's segment from the playbook counters (best win rate, with some exploration). With the brain off it picks a default. Over time the team learns, for example, that "motivated" private sellers fold to *fast cash pickup* while "price-anchored" sellers fold to *cite three comps*.
- **Preference learning:** each owner approve or reject updates `dealer` notes. The scout's filter tightens, so the approval rate goes up.
- **Counterparty memory:** repeat sellers (wholesalers, auction consignors) are remembered. Last time's floor becomes this time's opening anchor.

---

## 7. NVIDIA, NemoClaw, OpenShell, Crusoe and You.com: where each one shows up on screen

| Sponsor tech | What we use it for | Visible demo moment |
|---|---|---|
| **NVIDIA NemoClaw** | Installs and runs the dealer's always-on agent on the dealer's own machine (`nemoclaw onboard`). An OpenClaw concierge agent lives in the sandbox and talks to the owner through a messaging channel. | Terminal: `nemoclaw list` shows the `dealer` sandbox running. Phone: Telegram message *"Approve 2019 Tacoma at $17,900? Est. margin 17%. Reply YES D-102."* |
| **NVIDIA OpenShell** | Sandbox with a YAML network policy. Egress is allowed only to Crusoe inference, You.com and the dealer storefront. Everything else is blocked and surfaces for operator approval. Inference credentials stay in the OpenShell gateway, outside the sandbox. | **Scam moment:** a simulated seller sends a "verify payment" link to an unknown domain. The agent tries to open it, OpenShell blocks it, and the request shows up for operator review. The brain writes a red flag on that seller. |
| **NVIDIA Nemotron** (Nemotron 3 / 3.5 family) | **Super 120B** for negotiation and appraisal reasoning (Ultra 550B if `/v1/models` shows it for our project). **3.5 Lightning** for the librarian and the simulated sellers and buyers. **Nano 30B** for extraction and classification. **Nano Omni** for listing-photo condition checks (image input confirmed; stretch). Optional local Nemotron for private dealer data (stretch). Roles are spread across models on purpose, because Crusoe rate limits are per model. | A model badge on each agent action shows which Nemotron handled it. |
| **Crusoe Managed Inference** | Hosts every Nemotron call through an OpenAI-compatible API at `https://api.inference.crusoecloud.com/v1` (`backend/llm.py`). | Latency and token counter in the footer. A burst of parallel negotiations shows throughput. |
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
                 Owner's phone (Telegram)          Owner's browser (React dashboard)
                          |                                     |
  +----------- Dealer's machine ---------------------------------------------------+
  |  NemoClaw  ->  OpenShell gateway (holds Crusoe + You.com keys, enforces policy)  |
  |                 |                                                                |
  |   +------------ OpenShell sandbox "dealer" (network policy: allowlist only) ---+ |
  |   |  OpenClaw Concierge  --skill-->  Dealer API (FastAPI)                      | |
  |   |                                     |-- swarm.py  (shift loop, deal queue) | |
  |   |                                     |-- agents.py (scout ... librarian)    | |
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
| 0:35 | **Start a shift** | Dashboard: Joe's profile comes from the brain. Click **Start shift** (or text "go find me Tacomas" on Telegram). |
| 0:50 | **Live sourcing** | Scout feed fills with **real** listings from You.com Search. Appraiser card shows a **cited** You.com Research valuation. |
| 1:15 | **Negotiation with memory** | Split view: chat with a simulated seller next to **Recalled:** chips ("motivated sellers: fast-cash pickup wins 7/9", "Joe's max on this car: $18.4k"). The offer lands. |
| 1:45 | **Scam blocked** | Another seller sends a "payment verification" link. The agent tries to open it and **OpenShell blocks it**. The block shows in the operator view, and a red flag appears on that seller in the Brain tab. |
| 2:05 | **Owner approves from phone** | Telegram: "Approve $17,900?" The owner replies YES. Pipeline card moves to Bought, then In transit, with a shipping quote from You.com search. |
| 2:20 | **Sell side** | Merchandiser publishes the listing to Joe's storefront page. A simulated buyer haggles and the Closer sells above the target margin. |
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
- Real purchases, real payments, real contact with sellers, title and DMV paperwork.
- Scraping sites that block bots. If You.com doesn't return a listing, we don't chase it.
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
| Telegram channel flaky | Medium | The dashboard has the same Approve button, so the demo works without the phone. |
| LLM returns broken JSON | High | `chat_json` retries once, then a safe default. Offers are always clamped in code. |

---

## 14. Verify at T+0 (assumptions to check before building on them)

1. NemoClaw installs on our host (`nemoclaw host probe`) and `nemoclaw onboard` accepts a **compatible OpenAI endpoint** (Crusoe base URL, key and Nemotron model).
2. How to add our own network policy entries (`nemoclaw <name> policy list` / `policy add`) and where blocked requests surface for approval (`openshell term` or the dashboard).
3. Whether code inside the sandbox can call OpenShell's managed inference route (`inference.local`) so our backend never holds a key.
4. Crusoe base URL is `https://api.inference.crusoecloud.com/v1`. The current `.env.example` still has the old `api.crusoe.ai` host, which the team skill says to avoid. Confirm exact Nemotron IDs with `GET /v1/models`: Super `nvidia/Nemotron-3-Super-120B-A12B`, Lightning `nvidia/nemotron-3.5-lightning-30b-a3b`, Nano `nvidia/Nemotron-3-Nano-30B-A3B`, Nano Omni `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`, and Ultra (`nvidia/NVIDIA-Nemotron-3-Ultra-550B`, possibly not enabled for us). Source of truth: `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md`.
5. You.com key works on all three endpoints (`X-API-Key` header) and the account has credits.
6. Which messaging channel NemoClaw supports most reliably for our agent (target: Telegram).

---

## 15. References

- Team Crusoe skill (endpoint, model IDs, rate limits, reasoning toggles): `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md`
- Build roadmap: `agents/plans/roadmap.md`
- NemoClaw overview (OpenClaw): https://docs.nvidia.com/nemoclaw/user-guide/openclaw/about/overview.md
- NemoClaw command reference: https://docs.nvidia.com/nemoclaw/user-guide/openclaw/reference/commands
- Crusoe: Nemotron 3 Ultra on Crusoe Managed Inference: https://www.crusoe.ai/resources/blog/nvidia-nemotron-3-ultra-langchain-deep-agents-on-crusoe-managed-inference
- Crusoe Managed Inference docs: https://docs.crusoecloud.com/managed-inference/overview
- You.com API quickstart: https://you.com/docs/quickstart
