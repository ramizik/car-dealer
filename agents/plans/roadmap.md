# Dealer: 6-hour build roadmap (Shared Brain track)

**Status (2026-10-17, after the demo redesign):** P0 to P3 are done in code, and P4 (the eval number) is measured. The dashboard now has a single **Start Demo** button that runs a simulated 8-hour shop day in ~5 minutes with up to 4 deals at once, buying and selling together. Crusoe, You.com, NemoClaw on the droplet, and the brain OFF vs ON eval all run. The live seller call and NVIDIA speech are built and their pieces pass, but the full live call in the browser is not yet verified. P5 (hardening, rehearsals, backup video) has not started. Details in "Current state" below.

## Current state (2026-10-17)

**Works (verified in this repo or on the droplet):**
- Brain, LLM tiers with throttle and backoff, You.com wrapper with disk cache, simulator (`sim.py`). Offline tests: `test_brain.py` and `test_memory_tiers.py` pass.
- Eval: `EVAL_SEED=1` and `EVAL_SEED=2`, `SIM_FAST=1 python eval.py`, about 20 s, brain OFF vs ON on 10 held-out sellers. Seed 1 is stored in `backend/data/eval_result.json`.
- Demo workday in `swarm.py` (`_workday`) with `ops.py`: scout, appraise, negotiate, approval, logistics, storefront, sell, librarian. Length `DEMO_SHIFT_SECS` (300), parallel cars `DEMO_PARALLEL` (4), arrivals every 2-5 s. Restart resumes from `data/state.json`.
- Auto vs ask: buys and sales with profit at least 2x the dealer's minimum go through alone; the rest wait under Needs you. 3 cars are on the lot at shift start so buyer offers come in at once.
- Shift page: one Start Demo button with a 6-step summary, shop clock, Needs you rows with inline Buy / Sell buttons, deal board lanes (Buying, Coming in, For sale, Sold, Stopped).
- Real Craigslist listings in the scout (`craigslist.py`, `gen_inventory.py`), with synthetic inventory as the demo pool.
- NemoClaw concierge in the sandbox on the droplet: start shift, briefing, scam domain blocked.
- NVIDIA speech and embeddings pass `python backend/nvidia_check.py`: key, Parakeet ASR (`parakeet-tdt-0_6b-v2`), Magpie TTS (`Magpie-Multilingual.EN-US.Aria`), a TTS to ASR round trip, and embeddings (`nvidia/nemotron-3-embed-1b`).
- Live seller call (`live.py`): about 5 s into the demo one car's seller waits for an answer from the browser (a car dropped before the call hands it to the next). Endpoints `POST /deals/{id}/seller-audio`, `POST /deals/{id}/seller-text`, `GET /clips/{id}.wav`. After 60 s unanswered the simulated seller carries the rest of the call.
- Twilio phone line removed (`fa79d08`).

**Not tested yet:**
- The live call in the browser: recording with the mic, the turn banner, agent audio playback, and the typed fallback. The new Shift page was typechecked and run against the mock backend only, never viewed in a browser. This is the top risk.
- Parallel deals with the real model: Crusoe RPM (30 without a payment method) may throttle 4 deals at once; watch for slow rounds.
- The live path with real speech: browser WAV to Parakeet, and agent lines to Magpie inside a real negotiation. Only the standalone round trip has run.
- Mic access on a non-localhost origin. The browser requires HTTPS there, and nothing is set up for it.
- The droplet frontend: the dashboard is not served from the droplet yet, so the demo runs from a laptop on localhost against the droplet API (or the backend locally).
- Eval with seeds beyond 1 and 2, and the eval transcripts review (4.4 and 4.5).
- Degraded mode (5.2): no automatic switch to mock text after repeated LLM failures.
- `DEMO_MODE=1` end to end on a fresh clone.

**Next steps, in order:**
1. Run `python backend/nvidia_check.py` on the machine that will do the demo, then press Start Demo on localhost and answer the Live call with the mic and by typing. Check the Needs you rows and the board. Fix whatever breaks. Set `DEMO_PACE_MIN/MAX` (about 2 and 5) so parallel deals are readable.
2. Check the droplet path: either serve the frontend and tunnel the API, or run the backend locally against the droplet concierge.
3. Degraded mode (5.2) and a `DEMO_MODE=1` dry run (5.1, 5.3).
4. Two rehearsals and a backup video (5.5). Pre-flight checklist (5.6).
5. Decide on 4.4 and 4.5: read three transcripts per condition, and run seeds 3 and 4 if time allows. Never tune the simulator to the held-out set.

Companion to `docs/project-idea.md`. Crusoe endpoint, model IDs and rate limits: `.claude/skills/crusoe-recursive-agents-hackathon/SKILL.md` (source of truth). Times are hackathon clock, **T+0:00 to T+6:00**.
Every step has an owner lane, the file it touches. If a step's timebox runs out, take its fallback and move on.

---

## 0. Ground rules

- **One track:** Shared Brain. Anything that doesn't make the brain visible, the gain measurable, or the sponsor stack visible gets cut.
- **Always demoable:** mock mode (no keys) and demo mode (cached You.com + frozen brain) must keep working after every merge.
- **Feature freeze at T+4:30.** After that, only fixes, demo mode, rehearsal and pitch work.
- **Commit small and often to `main`.** Each lane owns its files, so there are no merge fights.
- **Never commit `.env`, keys or Telegram tokens.** Scratch notes go in `%TEMP%`, not the repo.
- **Real people are never contacted.** Real listings are read-only, and every counterparty is simulated.

### Lanes (2 teammates)

| Person | Lanes | Owns | Files |
|---|---|---|---|
| **1: Backend** | B + D | Shared brain, agents, swarm loop, API, You.com, simulator, eval | `backend/*` |
| **2: NVIDIA + dashboard** | A + C | NemoClaw/OpenShell sandbox and policy, concierge, React UI, demo flow, pitch | `nemoclaw/`, `.env.example`, `frontend/src/*` |

Step IDs keep their original lane letter (A/B/C/D) so history stays readable. A = Person 2, B = Person 1, C = Person 2, D = Person 1.

**Status legend:** `[x]` done, `[~]` partial, `[ ]` todo. Update the box in the same commit as the work.

### Critical path

`brain.py` → `sim.py` → `agents.negotiator` → `eval.py` → **headline number**. The NemoClaw work runs in parallel the whole time, and it has the highest risk, so it starts at minute 1.

---

## Timeline at a glance

| Clock | Phase | Gate (must be true to move on) |
|---|---|---|
| T+0:00 to 0:30 | **P0 Kickoff and de-risk** | Keys work, model IDs confirmed, NemoClaw install started |
| T+0:30 to 1:30 | **P1 Foundations** | Brain, LLM tiers, You.com wrapper, simulator each work alone. NemoClaw sandbox is up. |
| T+1:30 to 2:45 | **P2 Swarm pipeline + API** | One deal goes source → sold through the API with the real LLM. Plan A/B decided at T+2:00. |
| T+2:45 to 3:45 | **P3 Dashboard + NVIDIA moments** | UI shows the full flow. OpenShell block and phone approval both work. |
| T+3:45 to 4:30 | **P4 Eval and the number** | Brain OFF vs ON measured on held-out scenarios and shown in the UI |
| **T+4:30** | **FEATURE FREEZE** | |
| T+4:30 to 5:20 | **P5 Harden + demo mode** | Two clean rehearsals, backup video recorded |

---

## P0: Kickoff and de-risk (T+0:00 to 0:30). Everyone.

| Done | # | Lane | Step |
|---|---|---|---|
| [ ]  0.1 | All | Read `docs/project-idea.md` §1, §6, §10 together (5 min). Agree on demo persona "Joe's Auto, Stockton CA". |
| [x]  0.2 | A | **Start the NemoClaw install now. It's the longest pole.** Pick the host: a Linux machine, or Windows 11 + WSL2 Ubuntu + Docker. Install OpenShell, then NemoClaw, following the official quickstart. Run `nemoclaw host probe`. |
| [x]  0.3 | B | Read the Crusoe skill (§6 rate limits, §12 troubleshooting). Fix `.env.example`: `CRUSOE_BASE_URL=https://api.inference.crusoecloud.com/v1`, because the old `api.crusoe.ai` host causes 429s. Copy it to `.env` and add `CRUSOE_API_KEY`. Run `GET /v1/models` and record the **exact** IDs plus `features` (tool_calling, structured_outputs) for Super, Lightning, Nano, Nano Omni, and Ultra if listed. Time one chat call per model. **Add a payment method to the Crusoe project if possible: 30 RPM per model without one, 600 with one.** |
| [x]  0.4 | D | Get the You.com key. `curl` all three endpoints with header `X-API-Key`: `POST https://ydc-index.io/v1/search`, `POST https://ydc-index.io/v1/contents`, `POST https://api.you.com/v1/research` (`research_effort: "lite"`). Time Research. _Live: search, contents and research all run in shifts (2026-10-17)._ |
| [x]  0.5 | C | `npm install`, run the frontend, and confirm the current boilerplate renders against the backend in mock mode. |
| [x]  0.6 | B | Update `CLAUDE.md` context: the track is now **Shared Brain only**, and the layout section matches the files in this roadmap. |
| [x]  0.7 | All | Agree on the **API contract** (§P2 table) and the **event shape**. C builds against fixtures and doesn't wait for B. |

**Event shape (shared by everyone):**
```json
{"id": 42, "ts": 1760700000.1, "deal_id": "D-102", "agent": "negotiator",
 "type": "message|recall|write|state|blocked|approval|error",
 "text": "Offered $17,400 citing 3 comps", "data": {}, "model": "nemotron-3-super"}
```

**Deal states:** `sourced → appraised → negotiating → awaiting_approval → bought → in_transit → delivered → listed → sold`, plus `dropped` (with a reason).

---

## P1: Foundations (T+0:30 to 1:30)

### Lane B: Shared brain + LLM tiers

| Done | # | Step | File |
|---|---|---|---|
| [x]  1.B1 | Create `brain.py`, which replaces `memory.py`. Storage is `data/brain/events.jsonl`, append-only, under an `asyncio.Lock`. | `backend/brain.py` |
| [x]  1.B2 | `write(agent, scope, key, kind, value, source="", confidence=0.5, attr=None)`. Scopes are `dealer`, `party`, `market`, `playbook`. Kinds are `fact`, `obs`, `counter`, `note`. | same |
| [x]  1.B3 | Pure reducer `view(events) -> dict`, with merge rules: **counter** values summed; **obs** capped at 200, median, 30-day TTL; **fact** resolved by highest confidence then newest, with a conflict record when two facts at confidence ≥0.7 disagree; **note** deduped by normalised text and capped (50 per party, 30 for the dealer). | same |
| [x]  1.B4 | **Order-independence test:** shuffle 200 random events 20 times and assert an identical `view()`. This backs the "conflict-free" claim on stage. | `backend/test_brain.py` |
| [x]  1.B5 | `recall(scopes, keys, tags=None, budget_chars=1500) -> list[str]`. Rank by exact key match, then confidence, then recency, and stop at the budget. Each recall emits a `recall` event (for the UI chips). | same |
| [x]  1.B6 | `ENABLED` flag (brain OFF: `recall` returns `[]` and `write` is a no-op), plus `snapshot(name)` and `load(name)` into `data/brain/snapshots/`. | same |
| [x]  1.B7 | `stats()`: event count, bytes, per-scope counts, conflicts. This feeds the "lean" meter. | same |
| [x]  1.B8 | `llm.py`: add a `tier="smart"\|"fast"\|"sim"` argument mapped to `CRUSOE_MODEL_SMART` / `CRUSOE_MODEL_FAST` / `CRUSOE_MODEL_SIM`. Add a `CRUSOE_BASE_URL` override (for OpenShell's `inference.local` in Plan A). Add one retry on bad JSON. Record per-call latency and model for the footer. Keep mock mode, and add mock answers for the new prompts. | `backend/llm.py` |
| [x]  1.B9 | `llm.py` rate-limit and reasoning safety (see Crusoe skill §6, §7.2, §12): a **per-model** `asyncio.Semaphore` sized to the RPM tier; throttle on the `x-ratelimit-remaining-requests` header; jittered exponential backoff on 429/503 (max 4 tries); `max_tokens` ≥ 1024 on reasoning calls; `chat_template_kwargs: {"enable_thinking": false}` on fast extraction calls; if `content` is empty, check `finish_reason == "length"` and read `reasoning_content` defensively. | `backend/llm.py` |

**Brain record examples (for fixtures):**
```json
{"agent":"owner","scope":"dealer","key":"joes-auto","kind":"fact","attr":"max_mileage","value":110000,"confidence":1.0,"source":"onboarding"}
{"agent":"negotiator","scope":"party","key":"seller:S-07","kind":"note","value":"Moving to Reno on the 25th; wants cash, fast pickup","confidence":0.7,"source":"chat:D-102"}
{"agent":"appraiser","scope":"market","key":"toyota-tacoma-2019-trd","kind":"obs","attr":"private_value","value":24100,"source":"https://...","confidence":0.8}
{"agent":"negotiator","scope":"playbook","key":"fast_cash_pickup|motivated_private","kind":"counter","value":{"tries":1,"wins":1}}
```

### Lane D: You.com wrapper + simulator

| Done | # | Step | File |
|---|---|---|---|
| [x]  1.D1 | `youcom.py`: `search(query, count=10)`, `contents(urls)`, `research(question, effort="lite")` using `httpx.AsyncClient` with a 30s timeout (90s for Research). | `backend/youcom.py` |
| [x]  1.D2 | **Disk cache:** key = sha1(endpoint + payload), stored in `data/cache/*.json`. `DEMO_MODE=1` reads only from the cache. On error, return an empty result and emit an `error` event. **Never raise.** | same |
| [x]  1.D3 | Scout query templates. Base: `"{year_from}-{year_to} {make} {model} for sale near {city} under ${max_price}"`. Try variants that point at listing sites (cars.com, autotrader, cargurus, craigslist, bringatrailer, carsandbids, copart, iaai). Record which ones return **individual listing pages**. | `backend/youcom.py` |
| [x]  1.D4 | `extract_listing(markdown)`: the Nano model returns JSON `{year, make, model, trim, miles, price, city, title_status, vin, url, photo_urls}`. Drop the listing if price or miles is missing. | `backend/youcom.py` (moved out of `agents.py` so the lanes don't collide; also `extract_listings`, `fetch_listings`) |
| [x]  1.D5 | Save 5–8 parsed real listings to `data/seed_listings.json`. **This is the guaranteed fallback** if Search goes thin on stage. | `backend/data/seed_listings.json` |
| [x]  1.D6 | `sim.py` **seller**: `Seller(ask, floor, persona, patience, seed)`. Personas: `motivated_private`, `price_anchored`, `haggler`, `wholesaler_repeat`, `scammer`. Each persona has a hidden `weak_to` tactic and leaks text hints ("need it gone before I move", "KBB says it's worth..."). | `backend/sim.py` |
| [x]  1.D7 | Seller step rule (deterministic). `eff_floor = floor * (0.94 if tactic == weak_to else 1.0)`. Accept if `offer >= eff_floor`. Otherwise counter at `max(eff_floor, last_counter - (last_counter - eff_floor) * rate[persona])`. Walk away after `patience` rounds. The `scammer` sends a payment link on round 2 and never sells. | same |
| [x]  1.D8 | Seller **text**: templated in `SIM_FAST=1` (for eval). Otherwise Nano rewrites the template into natural language without changing the numbers. | same |
| [x]  1.D9 | `sim.py` **owner**: hidden true preferences (for example rejects >2 owners or rebuilt title, likes 4x4) → `approve(candidate) -> bool`. **buyer**: hidden max price plus persona, mirroring the seller. | same |
| [x]  1.D10 | `scenarios(seed, n)`: pairs real or seed listings with generated sellers. Fixed split: **20 train, 10 held-out**, with no shared seller IDs except deliberate `wholesaler_repeat` repeats. | same |

> **Integrity rule:** the persona → tactic mapping lives **only** in `sim.py`. Agents never see it. They must discover it through the brain. Say this in the pitch.

### Lane A: NemoClaw sandbox up

_**Live (2026-10-17):** DigitalOcean droplet, sandbox `dealer` (OpenClaw) on Crusoe `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B` via compatible-endpoint; agent answers through `inference.local`. Presets applied: `dealer-apis` (You.com), `dealer-api-host` (backend at private IP 10.120.0.2:8000, `host.openshell.internal` was rejected as internal). Skill `dealer-concierge` installed and ready. Checked from inside the sandbox: backend port returns 200, the scam domain is blocked. Plan A/B decision: backend runs on the droplet host and only the concierge is sandboxed. Backend deployed on the droplet (`/root/dealer`, `.venv`, `DEMO_MODE=1`, bound to 10.120.0.2:8000, log at `/root/backend.log`). **End-to-end check passed:** the concierge in the sandbox, running Nemotron, called `POST /shift/start` and `GET /deals` and answered "2 deals awaiting approval". 3.A1 scam rehearsal, 3.A3 briefing and 3.A4 beauty shot passed on the droplet (see `nemoclaw/SETUP.md`). Gateway linger enabled so the sandbox survives SSH disconnects. Remaining: exposing the dashboard (run the frontend against the droplet or tunnel the API)._

_Repo side done: `nemoclaw/SETUP.md` (runbook, docs-checked commands), `nemoclaw/presets/dealer-apis.yaml` (You.com egress), `nemoclaw/presets/dealer-api-host.yaml` (Plan B host API), `nemoclaw/skills/dealer/SKILL.md` (concierge, name `dealer-concierge`). Host side blocked on: WSL2 Ubuntu install (admin and reboot), the Crusoe key in the onboarding shell, and a Telegram bot token from @BotFather. The concierge also needs the B endpoints `/shift/*`, `/deals/*`, `/briefing` and `PUT /dealer`._

| Done | # | Step | File |
|---|---|---|---|
| [x]  1.A1 | `nemoclaw onboard --name dealer` (agent: `openclaw`). Inference provider: **compatible OpenAI endpoint** with Crusoe base URL, key and the Nemotron SMART model ID. (For non-interactive runs, check `NEMOCLAW_PROVIDER` / `NEMOCLAW_MODEL` in the docs.) | `nemoclaw/SETUP.md` (commands only, no secrets) |
| [x]  1.A2 | Talk to the OpenClaw agent in the sandbox (`nemoclaw launch dealer` or connect, whichever the docs show). Ask it "what model are you running on?" | same |
| [x]  1.A3 | `nemoclaw dealer policy list`. Find out how to add custom egress entries and where blocked requests surface (`openshell term` or the dashboard). | same |
| [x]  1.A4 | Write `nemoclaw/dealer-policy.yaml` (or a preset): allow `ydc-index.io`, `api.you.com`, the Crusoe inference host, `api.telegram.org`, and the dealer API host. Deny everything else. | `nemoclaw/dealer-policy.yaml` |
| [cut]  1.A5 | **Cut: no Telegram, owner approves in the dashboard.** Create the Telegram bot (team member uses BotFather themselves) and keep the token in `.env` only. Configure the Telegram channel in NemoClaw onboarding or the channel command. | `.env` (not committed) |

**Timebox 1.A1–1.A5 to T+1:45.** If NemoClaw won't install on our hardware by then, try a Linux cloud VM for 20 minutes. If that fails too, use the **Plan B-lite** fallback in §P2-A.

**Gate P1 (T+1:30):** brain test passes. You.com returns real listings and a cited valuation. `sim.Seller` negotiates deterministically. The NemoClaw concierge answers a message.

---

## P2: Swarm pipeline + API (T+1:30 to 2:45)

### Status snapshot (2026-10-17)

Working in code:
- `brain.py` (order-independent reducer, recall, snapshots) and `llm.py` (tiers, throttle, mock mode).
- `youcom.py`: live Search, Contents and Research, disk cache, `DEMO_MODE`.
- `craigslist.py` and `gen_inventory.py`: real listings for the scout, synthetic inventory for the demo pool.
- `sim.py`: deterministic sellers, buyers and owner. `scenarios(seed, n)` gives the 20 / 10 split.
- `agents.negotiate`: segment classifier, tactic pick from the playbook, callback capture, scam-link block, voice hooks, live seller hook.
- `swarm.py` + `ops.py`: scout, appraise, negotiate, approval, logistics, storefront, sell, librarian. `/shift/*` endpoints. `data/state.json` resume.
- `live.py` + `voice.py`: live seller answer from the browser, Parakeet ASR, Magpie TTS, embeddings via `vector_memory.py`.
- `skills.py` plus `backend/skills/*/SKILL.md`: read-before in `negotiate`, mistake log writes.
- `eval.py`: brain OFF vs ON, `GET /eval`, `POST /eval/run`.
- Frontend: sections Shift, Buying, Inventory, Selling, Insights, Setup on the live API, with dark mode and the deal drawer. The live-seller turn banner and recorder are built (`TurnBanner.tsx`, `SellerTurn.tsx`) but not yet tested in a browser.

Not done:
- Ranking scout candidates by dealer notes (2.B2).
- Degraded mode after repeated LLM failures (5.2).
- The rehearsals, backup video and pre-flight checklist (P5).

### Lane B: Agents, shift loop, API

| Done | # | Step | File |
|---|---|---|---|
| [~]  2.B1 | `agents.py`: one async function per role. **Each starts with `brain.recall(...)` and ends with `brain.write(...)`.** No exceptions. Reviewers grep for it. | `backend/agents.py` |
| [~]  2.B2 | `scout(profile)`: You.com search, then contents, then extract. Rank by fit using dealer facts and dealer notes (learned rejections). Output top N candidates. Writes `market` observations for listing prices. _Live: You.com search and Craigslist listings, extracted and written to market. Ranking by dealer notes is not done._ | same |
| [x]  2.B3 | `appraise(listing)`: You.com Research (`lite`) asks for the fair private-party value and common issues for this year/model/miles/region. The Nano model extracts `{low, mid, high, issues[], sources[]}`. Writes `market` observations **with source URLs**. `max_buy = min(dealer.max_pct * retail_mid, mid * (1 - margin_target))`. _In `swarm._appraise`: You.com Research, Nano extract, sim prices rule when research disagrees, VIN risk check, writes market with citations._ | same |
| [x]  2.B4 | `classify_segment(seller_text)`: Nano returns `motivated_private \| price_anchored \| haggler \| wholesaler_repeat \| unknown`, with a keyword fallback. | same |
| [x]  2.B5 | `negotiate(deal)` loop (≤6 rounds). Recall `party:seller`, `playbook:*|segment` and the dealer max. **Tactic pick:** brain ON uses the best win rate with ε=0.15 in training and 0 in eval; brain OFF uses the default `anchor_low`. The SMART model writes the offer and message given the tactic, comps and memory. **Clamp the offer to `max_buy` in code.** Add the AI-disclosure line. Write a party note (summary, signals), a playbook counter (tries/wins) and a party fact (the seller's last counter, which becomes the anchor for repeat sellers). | same |
| [~]  2.B6 | `open_link(url)` tool. If seller text contains a URL, the negotiator "verifies" it with an `httpx` GET. On a proxy denial or connection error inside the sandbox, emit a `blocked` event ("Blocked by OpenShell policy") and write a `party` red-flag fact (confidence 0.9). Drop the deal. | same |
| [x]  2.B7 | `request_approval(deal)`: state becomes `awaiting_approval` and emits an `approval` event. The dashboard shows Approve / Reject (no Telegram). Optionally sends Telegram `sendMessage` with "Approve {car} at ${price}? Est. margin {m}%. Reply YES {deal_id}". | same |
| [x]  2.B8 | `logistics(deal)`: You.com search for "car transport cost {from} to {to}", extract a range, simulate booking. A simulated clock (`1 day = 3 s`) emits `in_transit`, then `delivered`. Writes a `market` shipping observation. | same |
| [x]  2.B9 | `merchandise(deal)`: recall "what sells" counters and comps. Price = comps mid × (1 + markup). SMART writes title, description and 5 bullet points. Publishes to `GET /storefront` (HTML). | same |
| [x]  2.B10 | `close_sale(deal)`: sim buyer negotiation, mirroring 2.B5 on the sell side, with a floor of cost × (1 + min margin). Writes buyer notes and sell playbook counters. | same |
| [x]  2.B11 | `librarian()`: every 5 deals, compact notes (Nano summarises per key), resolve easy conflicts, and log bytes before and after. _Done in `librarian.py` (lessons, mistakes, view-identical compaction); swarm runs it every 3 deals._ | same |
| [x]  2.B12 | `swarm.py`: a `shift` background `asyncio.Task` with an `asyncio.Semaphore(3)` deal pipeline. State is persisted to `data/state.json` so a restart resumes. Every agent action goes through `emit(event)` into an in-memory list plus `data/events.jsonl`. | `backend/swarm.py` |
| [x]  2.B13 | `main.py` endpoints (table below). Global exception handler returns `{"error": "..."}` and **never a stack trace**. | `backend/main.py` |

**API contract**

| Method + path | Purpose |
|---|---|
| `GET /health` | Liveness check, plus `demo_mode`, `brain_enabled`, `sandboxed` flags |
| `GET /dealer` / `PUT /dealer` | Read or update the dealer profile (written into the `dealer` scope as facts) |
| `POST /shift/start` `{query?, max_deals}` / `POST /shift/stop` | Start or stop the always-on shift |
| `GET /events?since={id}` | Feed (UI polls every 1s) |
| `GET /deals` / `GET /deals/{id}` | Pipeline and deal detail (chat, valuation, recalls) |
| `POST /deals/{id}/approve` `{yes: bool}` | Owner decision (from UI or concierge) |
| `GET /brain` | Views per scope, conflicts, stats, playbook table |
| `POST /brain/load/{snapshot}` | Load `cold` or `warm` for the demo |
| `POST /eval/run` / `GET /eval` | Run eval in the background / get the latest results |
| `GET /briefing` | Plain-text summary for the concierge ("Overnight: 2 bought, 1 scam blocked...") |
| `GET /storefront` | Dealer's public listing page (the "own resources" publishing target) |

### Lane A: Plan A attempt, then the concierge skill

| Done | # | Step | File |
|---|---|---|---|
| [x]  2.A1 | **Plan A:** run the dealer backend **inside** the sandbox. Options to try in order: (a) the onboard image flags (`--from` / `--from-image`) with a Dockerfile that adds Python and our backend; (b) install Python in the running sandbox and copy `backend/` in. Point `CRUSOE_BASE_URL` at the OpenShell-managed `inference.local` route so no Crusoe key is in the sandbox. | `nemoclaw/Dockerfile` (if used) |
| [x]  2.A2 | **T+2:00 decision. Write it in team chat.** Plan A works: keep it. Otherwise **Plan B:** backend on the host, and only the concierge is sandboxed. Allow the backend host in the policy. The scam link is then opened **by the concierge** ("check this link the seller sent"), which still gives a real OpenShell block. | team chat |
| [x]  2.A3 | Concierge skill: `nemoclaw/skills/dealer/SKILL.md` describing our API with curl examples (start shift, briefing, list deals, approve `D-xxx`, show brain highlights). Install it into the sandbox the way the docs describe. | `nemoclaw/skills/dealer/SKILL.md` |
| [cut]  2.A4 | **Cut: dashboard Approve/Reject replaces it.** Approval round trip. "YES D-102" on Telegram makes the concierge call `POST /deals/D-102/approve`. The concierge also writes the owner's free-text reasons ("too many owners") to `PUT /dealer` notes, which feeds preference learning. | skill |

**Plan B-lite (only if NemoClaw never comes up):** show `nemoclaw/dealer-policy.yaml` on screen, play a pre-recorded clip of the block from any working machine, and say so honestly. All dashboard features still work.

### Lane C: UI skeleton on fixtures (parallel)

| Done | # | Step | File |
|---|---|---|---|
| [x]  2.C1 | Fixtures `frontend/src/fixtures.ts`: 2 deals in different states, 30 events, a brain view with all 4 scopes plus 1 conflict, and an eval result. | `frontend/src/fixtures.ts` |
| [x]  2.C2 | Layout: header (dealer name, **Start shift**, demo-mode badge, "Sandboxed by OpenShell" badge from `/health`), tabs **Shift / Brain / Eval**, footer (model badges, average Crusoe latency). | `frontend/src/App.tsx` |
| [x]  2.C3 | `api.ts`: fetch wrapper that falls back to fixtures on error. **The UI never goes blank.** | `frontend/src/api.ts` |

**Gate P2 (T+2:45):** with real Crusoe and You.com, `POST /shift/start` takes at least one deal to `sold` through the API, with recall and write events logged. The scammer deal produces a `blocked` event. Plan A or B is decided and the concierge skill works.

---

## P3: Dashboard + NVIDIA moments (T+2:45 to 3:45)

### Lane C: The four screens judges see

| Done | # | Step |
|---|---|---|
| [x]  3.C1 | **Shift tab, left:** live event feed (poll `/events?since=`) with an agent icon or colour, model badge, and **red rows for `blocked`**. |
| [x]  3.C2 | **Shift tab, right:** pipeline columns by deal state. Cards show car, price, margin, and an **Approve / Reject** button when `awaiting_approval`. |
| [x]  3.C3 | **Deal drawer** (click a card): seller chat bubbles. Under each agent message, **"Recalled:" chips** taken from that turn's `recall` events. Valuation card with **You.com citations as links**. Tactic used. |
| [x]  3.C4 | **Brain tab:** 4 columns (Dealer / Parties / Market / Playbook). Playbook table shows win rate per tactic × segment. **Conflicts panel. Lean meter** (events, KB, before/after compaction). Snapshot buttons `cold` / `warm`. |
| [x]  3.C5 | **Eval tab:** paired bars, OFF vs ON, for each metric (plain CSS bars, no chart library). Headline number large. Per-scenario table underneath. "Re-run" button. |
| [x]  3.C6 | Empty, loading and error states for every panel. A wording pass on labels. |

### Lane A: Make the NVIDIA moments reliable

| Done | # | Step |
|---|---|---|
| [x]  3.A1 | Scam rehearsal: start a shift with a seeded `scammer` seller. Confirm (a) the OpenShell operator view shows the blocked domain, (b) the dashboard shows a red `blocked` row, (c) the Brain tab shows the red flag. The domain is under a reserved test TLD (for example `secure-escrow-verify.example.net`), so nothing real is contacted. |
| [cut]  3.A2 | **Cut: rehearse dashboard approval instead.** Phone approval rehearsal: approval message arrives on Telegram, "YES D-xxx" advances the deal, and the dashboard updates. |
| [x]  3.A3 | Morning briefing: the concierge answers "what happened overnight?" using `GET /briefing`. |
| [x]  3.A4 | Terminal "beauty shot" for the pitch: `nemoclaw list` + `nemoclaw dealer policy list` + the operator view, in one tidy terminal layout. |
| [cut]  3.A5 | **Cut: seed and cached listings carry no photo URLs, so a photo check would be invisible on stage.** **Stretch (only if all above is solid):** Nano Omni photo check in `appraise` (send listing photo URLs, get condition flags), **or** a local Nemotron route for private dealer data. Pick one and timebox to 30 minutes. |

### Lane D: Real-data polish

| Done | # | Step |
|---|---|---|
| [x]  3.D1 | Pre-warm the You.com cache for the exact demo queries (Joe's profile: Tacoma, 4Runner, RAV4, Tundra near Stockton). _Live shift on a throwaway brain cached appraisal, VIN, shipping and comps queries for every seed car (cache 50 -> 60 files, 10/10 deals with citations); `data/cache` copied to the droplet (git-ignored)._ |
| [x]  3.D2 | Check 3 Research valuations by hand against their cited sources. Fix the extraction prompt if numbers drift. _Checked 2008 RAV4 117k ($4.4k-8k, KBB), 2001 Tacoma 226k ($3.5k-6.5k, KBB/Edmunds), 2002 RAV4 144k (~$2.5k, Edmunds): numbers match sources, but sim asks sit above them. Fix: when the cited mid is >25% off the deal comps, the drawer shows it as an independent check plus "asking above cited range", and prices stay on sim numbers._ |

**Gate P3 (T+3:45):** someone outside the team watches one full shift on the dashboard and can describe what the brain did.

---

## P4: Eval and the number (T+3:45 to 4:30). Lane D (+B)

| Done | # | Step | File |
|---|---|---|---|
| [x]  4.1 | `eval.py`: `run(brain_enabled, scenarios)` drives `negotiate()` (and optionally scout→owner approval) with `SIM_FAST=1`. Parallelism comes from the per-model limiter in `llm.py` (1.B9). Same seeds in both conditions. **Call budget:** about 160 SMART calls (20 train + 2×10 held-out, ~4 rounds each). That takes ~6 min at 30 RPM and under 1 min at 600 RPM, so start the run early, or use a payment-method project. | `backend/eval.py` |
| [~]  4.2 | Protocol: (1) wipe the brain, (2) **train** on 20 scenarios with brain ON, ε=0.15, (3) snapshot `warm`, (4) **held-out** 10 with brain OFF, (5) **held-out** 10 with brain ON loaded from `warm`, ε=0. _Seeds 1 and 2 run as 20 train / 10 held-out; the warm snapshot step is not in the protocol yet._ | same |
| [~]  4.3 | Metrics per condition: **surplus captured** `mean((ask-paid)/(ask-floor))` over closed deals, **close rate**, **mean rounds**, **owner approval rate** (if scout eval is on), and a **scam deals avoided** count. _Surplus, close rate, rounds and scam count are measured. Owner approval rate is not._ | same |
| [ ]  4.4 | Run it. Read 3 transcripts per condition to make sure the gain comes from recall (tactic pick, repeat-seller anchor, learned preferences) and not from a bug. | — |
| [ ]  4.5 | If the gain is noisy: increase held-out to 20 and/or run 3 seeds and report mean ± range. **Never tune the sim to the held-out set.** | — |
| [~]  4.6 | Freeze: commit `eval_results.json` and the `cold` / `warm` snapshots. The UI shows the frozen result by default, and the "Re-run" button runs live. | `backend/data/` (decide whether to un-ignore these few files) |

> Write the headline sentence now, using the measured values only: *"On 10 held-out deals, with the brain on, the team captured __% of the negotiable surplus vs __% with it off, and closed __/10 vs __/10."*

---

## FEATURE FREEZE (T+4:30)

From here on: bug fixes, demo mode, copy, rehearsal. No new features. Anything unfinished gets cut using the cut list in §8.

---

## P5: Harden + demo mode (T+4:30 to 5:20)

| Done | # | Lane | Step |
|---|---|---|---|
| [~]  5.1 | B | `DEMO_MODE=1`: You.com from cache only, brain loads `cold` at shift start (so learning is visible) or `warm` for the Eval story, sim seeds fixed, simulated clock fast. |
| [x]  5.2 | B | Crusoe outage fallback: if 2 consecutive LLM calls fail, switch to mock answers for the negotiation text and keep the deterministic prices. A banner reads "degraded". _`llm.live()` gates all LLM text; 60 s cooldown (`LLM_DEGRADE_SECS`), `/health.llm_degraded`, UI banner._ |
| [ ]  5.3 | C | Demo script dry run #1 against §10 of `docs/project-idea.md`, timed. Note every stumble. |
| [ ]  5.4 | All | Fix the stumbles from 5.3 only. |
| [ ]  5.5 | C | Dry run #2, **recorded** (screen + phone) as the backup video. |
| [ ]  5.6 | A | Pre-flight checklist: sandbox running, policy applied, operator view open in its own terminal, phone charged and unlocked, notifications on. |
| [x]  5.7 | B | Reset script: `cd backend && python reset_demo.py` wipes deals and events and loads the `cold` snapshot. |

---

## 8. Cut list (cut from the top when behind)

1. Nano Omni photo check / local Nemotron privacy route (3.A5)
2. Telegram channel **posting** of listings (storefront page stays)
3. Closer sell-side negotiation (keep "listed" with a computed price)
4. Logistics timeline animation (single "transport booked" event)
5. Plan A in-sandbox backend (use Plan B)
6. Telegram approvals (the dashboard Approve button stays)
7. Owner-approval-rate metric in eval (keep negotiation metrics)

**Never cut:** visible recall chips, the measured OFF vs ON number, live You.com Search + Research with citations, the OpenShell block, one full deal end to end, a demo mode that never shows a blank screen.

---
