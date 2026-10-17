"""The shift: a simulated working day. Several deals run at the same time, each end to end, and keeps the state the dashboard reads.

Each deal: scout -> appraise -> negotiate -> owner approval -> logistics -> merchandise -> sale to a simulated buyer.
The workday compresses DEMO_SHIFT_SECS real seconds into 8 shop hours. Up to DEMO_PARALLEL cars are negotiated at once
while earlier cars ship, list and sell in the background. Clear wins are bought and sold without asking; borderline
ones wait for the dealer, and one seller phones in live. The librarian compacts the brain every few deals.
State is saved to data/state.json, so a restarted backend picks up shipments and listings where they were.
Prices come from code and the sim, never the LLM.
"""
import asyncio
import contextvars
import json
import os
import random
import time
from pathlib import Path

import agents
import conversations
import craigslist
import librarian
import live
import memory_layer
import brain
import llm
import skills
import youcom
from agent_tiers import tier_for
import dealer_profile
import dealer_memory
import seller_agent
import ops
import sim

DEALS: dict[str, dict] = {}
EVENTS: list[dict] = []
_SC: dict[str, dict] = {}  # deal id -> scenario (hidden buyer lives here)
_state = {"running": False, "task": None, "seed": 0, "n": 0, "cap": 0, "started": None, "ended": None,
          "phase": "idle", "deal": None, "continuous": False, "live": False, "live_done": False}
_sim_prev: dict[str, int] = {}  # deal id -> last shop minute stamped, so a fast deal still moves forward
SHIFT_SECS = float(os.getenv("DEMO_SHIFT_SECS", "300"))  # real seconds that stand for one 8-hour shop day
SHIFT_HOURS = 8
PARALLEL = int(os.getenv("DEMO_PARALLEL", "4"))  # cars negotiated at the same time
AUTO_PROFIT_X = 2.0  # buy or sell without asking when profit is at least this many times the dealer's minimum
MAX_DEALS = 80
_cur: contextvars.ContextVar = contextvars.ContextVar("deal", default=None)  # the deal the running task works on
_active: dict[str, str] = {}  # deal id (or "scout") -> what it is doing right now
STATE_FILE = Path(__file__).parent / "data" / "state.json"
_tasks: set = set()  # after-buy pipelines running alongside the next negotiation


def save() -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"deals": DEALS, "events": EVENTS, "scenarios": _SC,
                                   "state": {k: _state[k] for k in ("seed", "n")}}, default=str), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception:
        pass  # persistence is a bonus; never break the shift over it


def _restore() -> None:
    if not STATE_FILE.exists():
        return
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    DEALS.update(d.get("deals", {}))
    EVENTS.extend(d.get("events", []))
    _SC.update(d.get("scenarios", {}))
    _state.update(d.get("state", {}))
    for deal in DEALS.values():  # work cut off mid-negotiation can't be resumed honestly
        deal["turn"] = None
        if deal["state"] in ("sourced", "appraised", "negotiating"):
            deal.update(state="dropped", drop_reason="backend restarted mid-negotiation")
    for e in EVENTS:
        if e.get("deal_id") and isinstance(e.get("sim_min"), int):
            _sim_prev[e["deal_id"]] = max(_sim_prev.get(e["deal_id"], -1), e["sim_min"])


_restore()


def _shop_minute(ts: float) -> int | None:
    """Shop minutes since 8:00 AM. None when no shift is open."""
    if not _state["started"]:
        return None
    p = min(1.0, max(0.0, (ts - _state["started"]) / SHIFT_SECS))
    return int(p * SHIFT_HOURS * 60)


def emit(agent: str, type_: str, text: str, data: dict | None = None) -> None:
    data = data or {}
    ts = time.time()
    row = {"id": len(EVENTS) + 1, "ts": ts, "deal_id": data.get("deal_id"), "agent": agent,
           "type": type_, "text": text, "data": data}
    sim = _shop_minute(ts)
    if sim is not None and row["deal_id"]:
        prev = _sim_prev.get(row["deal_id"], -1)
        if sim <= prev:
            sim = prev + 1
        _sim_prev[row["deal_id"]] = sim
        row["sim_min"] = sim
    elif sim is not None:
        row["sim_min"] = sim
    EVENTS.append(row)


# Demo names for the admin page. "emits" are the names the agents use in the event feed and memory.
ROSTER = [
    {"name": "Sam", "role": "Scout", "emits": ["scout"], "phase": "scouting"},
    {"name": "Priya", "role": "Appraiser", "emits": ["appraiser"], "phase": "valuing"},
    {"name": "Marcus", "role": "Buyer agent", "emits": ["negotiator", "buyer"], "phase": "sourcing"},
    {"name": "Ivy", "role": "Librarian", "emits": ["librarian"], "phase": "tidying memory"},
    {"name": "Ruth", "role": "Logistics", "emits": ["logistics"]},
    {"name": "Omar", "role": "Merchandiser", "emits": ["merchandiser"]},
    {"name": "Leo", "role": "Seller agent", "emits": ["seller", "seller_agent"]},
]
RECENT_S = 120  # an agent counts as working if it logged something this recently


def roster() -> dict:
    """Who is working now: logged in the last two minutes, or doing a job in the active shift, plus memory writes."""
    now = time.time()
    phases = set(_active.values())
    last: dict[str, float] = {}
    for e in EVENTS:
        last[e["agent"]] = max(last.get(e["agent"], 0.0), e["ts"])
    writes: dict[str, int] = {}
    for e in brain.events():
        writes[e.get("agent", "")] = writes.get(e.get("agent", ""), 0) + 1
    rows, working = [], 0
    for a in ROSTER:
        seen = max((last.get(n, 0.0) for n in a["emits"]), default=0.0)
        busy = (now - seen < RECENT_S) or (a.get("phase") in phases)
        working += busy
        rows.append({"name": a["name"], "role": a["role"], "status": "working" if busy else "idle",
                     "last_seen_s": round(now - seen) if seen else None,
                     "memory_writes": sum(writes.get(n, 0) for n in a["emits"])})
    return {"working": working, "total": len(ROSTER), "shift_phase": _state["phase"], "agents": rows, "demo_names": True}


def _phase(phase: str, deal_id: str | None = None) -> None:
    """Mark what one task is doing. Many tasks run at once; the headline phase is the most recent change."""
    key = deal_id or _cur.get() or "scout"
    if phase == "idle":
        _active.pop(key, None)
    else:
        _active[key] = phase
    _state["phase"], _state["deal"] = phase, deal_id


def _on_brain(agent: str, kind: str, payload) -> None:
    """Brain writes become feed events so the dashboard shows what the team just learned."""
    if kind != "write" or not isinstance(payload, dict):
        return
    v = payload.get("value")
    val = v if isinstance(v, str) else ", ".join(f"{k}={x}" for k, x in v.items()) if isinstance(v, dict) else str(v)
    lock = f"(private to {', '.join(payload['visible_to'])}) " if payload.get("visible_to") else ""
    emit(agent or "librarian", "write", f"{lock}{payload.get('scope')} / {payload.get('key')}: {val}"[:200],
         {"scope": payload.get("scope"), "key": payload.get("key"), "kind": payload.get("kind"),
          "private_to": payload.get("visible_to"),
          "confidence": payload.get("confidence"), "deal_id": _cur.get()})


brain.listeners.append(_on_brain)

_YDC_AGENT = {"scouting": "scout", "sourcing": "scout", "valuing": "appraiser"}
_YDC_NAME = {youcom.SEARCH_URL: "Search", youcom.CONTENTS_URL: "Contents", youcom.RESEARCH_URL: "Research"}


def _on_youcom(kind: str, payload) -> None:
    """Live You.com calls and failures show up in the feed under the agent that made them."""
    if kind not in ("call", "error") or not isinstance(payload, dict):
        return
    if kind == "error" and "cache miss" in payload.get("error", ""):
        return  # demo mode / no key: quiet fallback to cache or seed data
    name = _YDC_NAME.get(payload.get("endpoint"), "API")
    text = f"You.com {name}: {payload['latency']}s" if kind == "call" else f"You.com {name} failed, using fallback"
    emit(_YDC_AGENT.get(_active.get(_cur.get() or "scout", ""), "system"), "state", text,
         {"deal_id": _cur.get(), "tool": "you.com", **payload, "endpoint": name})


youcom.listeners.append(_on_youcom)


def clock() -> dict:
    """The simulated shop clock: SHIFT_HOURS of shop time spread over SHIFT_SECS real seconds."""
    if not _state["started"]:
        return {"progress": 0.0, "sim_minutes": 0, "sim_hours": SHIFT_HOURS}
    end = _state["ended"] or time.time()
    p = min(1.0, (end - _state["started"]) / SHIFT_SECS)
    return {"progress": round(p, 4), "sim_minutes": int(p * SHIFT_HOURS * 60), "sim_hours": SHIFT_HOURS}


def status() -> dict:
    busy = [k for k in _active if k != "scout"]
    return {k: _state[k] for k in ("running", "n", "cap", "started", "ended", "phase", "deal", "continuous", "live")} | {
        "background": len(_tasks), "demo": True, "active": len(busy), "parallel": PARALLEL,
        "scouting": "scout" in _active, "shift_secs": SHIFT_SECS, **clock()}


def running() -> bool:
    return _state["running"]


def _title(l: dict) -> str:
    if l.get("title"):  # real Craigslist listing
        return l["title"]
    return f"{l.get('year', '')} {l.get('make', '')} {l.get('model', '')} · {int(l.get('miles') or 0) // 1000}k mi".strip()


def _chat(result: dict) -> list[dict]:
    return [agents.bubble(t) for t in result.get("transcript", []) if t["from"] in ("agent", "seller") and t.get("text")]


APPRAISE_SYSTEM = ("Extract a used-car market value from research text. Return JSON "
                   '{"low": int, "mid": int, "high": int, "issues": [short strings]}. Dollars, no text.')


async def _scout() -> None:
    """Scout: real listing URLs via You.com (cache in DEMO_MODE), seed listings if search is empty."""
    skills.load("buyer/marketplace")
    try:
        items = await youcom.find_listing_urls(dealer_profile.get() if isinstance(dealer_profile.get(), dict) else {}, limit=6)
        found = await youcom.fetch_listings(items) if items else []
    except Exception:
        found = []
    found = found or youcom.seed_listings()
    for l in found[:6]:
        brain.write("scout", "market", f"listing:{l.get('make', '')} {l.get('model', '')}".lower(), "obs",
                    {"price": l.get("price"), "miles": l.get("miles"), "url": l.get("url")}, source=l.get("url") or "seed")
    live = [l for l in found[:6] if (l.get("url") or "").startswith("http")]
    emit("scout", "state", f"Scanned market via You.com: {len(found)} listings" + ("" if live else " (seed fallback)"),
         {"count": len(found), "citations": [{"url": l["url"], "title": _title(l)} for l in live[:4]]})


RESEARCH_TOLERANCE = 0.25  # cited mid this far from the deal's comps = shown as a check, not used for price


async def _appraise(deal: dict) -> None:
    """Appraiser: You.com research (lite, search fallback) -> Nano extracts a range; keeps the sim range if it
    disagrees. Also a You.com check on the VIN for stolen/salvage/scam reports."""
    skills.load("buyer/kbb")
    key = f"value:{deal['car'].split(' · ')[0]}".lower()
    known = brain.recall(["market"], keys=[key], agent="appraiser")
    listing = (_SC.get(deal["id"]) or {}).get("listing") or {}
    r, risk = await asyncio.gather(youcom.market_value(deal["car"]), youcom.risk_check(listing))
    if r.get("sources"):
        deal["valuation"]["citations"] = r["sources"][:4]  # cited even when the numbers below are not used
    try:
        if not r.get("content"):
            raise ValueError("no research")
        v = await llm.chat_json(APPRAISE_SYSTEM, r["content"][:4000], tier=tier_for("appraiser"))
        lo, mid, hi = (int(v.get(k) or 0) for k in ("low", "mid", "high"))
        if not (0 < lo <= mid <= hi):
            raise ValueError("implausible")
        if abs(mid - deal["valuation"]["mid"]) > deal["valuation"]["mid"] * RESEARCH_TOLERANCE:
            # Sim prices rule the deal, but the cited range is shown as an independent check, never hidden.
            deal["valuation"]["research"] = {"low": lo, "mid": mid, "high": hi}
            deal["valuation"]["issues"] = (v.get("issues") or []) + (
                [f"asking ${deal['asking']:,} is above the cited ${lo:,}-${hi:,} range"] if deal["asking"] > hi else [])
            brain.write("appraiser", "market", f"research:{key[6:]}", "obs", float(mid), attr="cited_mid", confidence=0.7,
                        source=deal["valuation"]["citations"][0]["url"] if deal["valuation"]["citations"] else "you.com")
        else:
            deal["valuation"].update(low=lo, mid=mid, high=hi, issues=v.get("issues") or [])
    except Exception:
        pass
    val = deal["valuation"]
    brain.write("appraiser", "market", key, "obs", {"low": val["low"], "mid": val["mid"], "high": val["high"]},
                source=(val["citations"][0]["url"] if val["citations"] else "comps"), confidence=0.6)
    if risk.get("flags"):
        val["risk"] = risk
        val["issues"] = list(val.get("issues") or []) + [f"web reports: {', '.join(risk['flags'])}"]
        brain.write("appraiser", "market", f"risk:{key[6:]}", "fact", ", ".join(risk["flags"]), attr="web_flags",
                    confidence=0.5, source=risk["sources"][0]["url"] if risk["sources"] else "you.com")
    emit("appraiser", "state", f"Valued {deal['car']} at ${int(val['mid']):,}"
         + (f", {len(val['citations'])} You.com sources" if val["citations"] else "")
         + (f", web flags: {', '.join(risk['flags'])}" if risk.get("flags") else "")
         + (f" ({len(known)} past notes)" if known else ""),
         {"deal_id": deal["id"], "sources": len(val["citations"]), "citations": val["citations"], "flags": risk.get("flags", [])})


MAX_BUYERS = 8  # buyers tried per car before it waits for a fresh shift
SALE_EVENTS: dict[str, asyncio.Event] = {}  # deal_id -> set when the dealer answers a sale
SALE_ANSWER: dict[str, bool] = {}


async def _ask_sale(deal: dict, price: int) -> bool:
    """A buyer accepted. Every sale waits for the dealer's yes, even a clear win. Returns the answer."""
    ev = asyncio.Event()
    SALE_EVENTS[deal["id"]] = ev
    SALE_ANSWER.pop(deal["id"], None)
    deal["state"], deal["sale_offer"] = "awaiting_sale", price
    emit("buyer", "approval", f"Buyer will pay ${price:,} for {deal['car']}. Your OK to sell?",
         {"deal_id": deal["id"], "price": price})
    await ev.wait()
    SALE_EVENTS.pop(deal["id"], None)
    return SALE_ANSWER.pop(deal["id"], False)


def sale_decision(deal_id: str, yes: bool) -> bool:
    """Dealer answer to a sale. False if nothing is waiting for one."""
    deal, ev = DEALS.get(deal_id), SALE_EVENTS.get(deal_id)
    if not deal or deal.get("state") != "awaiting_sale" or ev is None:
        return False
    SALE_ANSWER[deal_id] = bool(yes)
    ev.set()
    emit("owner", "state", f"{'Approved' if yes else 'Declined'} the sale of {deal['car']} at ${deal['sale_offer']:,}",
         {"deal_id": deal_id})
    return True


def _sell_floor(deal: dict) -> int:
    """Lowest price that keeps the dealer's minimum profit: what we paid + recon + their minimum (from setup)."""
    return int(round(deal["bought_for"] + seller_agent.RECON + seller_agent.min_profit(), -1))


async def _sell(deal: dict, buyer: sim.Buyer) -> bool:
    """List at the resale quote and talk to one buyer. An accepted price waits for the dealer.
    Returns True when the car sells. A walk-away leaves it listed for the next buyer."""
    floor = _sell_floor(deal)
    price = max(int(deal["list_price"]), floor)
    party = f"buyer:{deal['id']}"
    emit("seller", "state", f"Listed {deal['car']} at ${price:,}", {"deal_id": deal["id"], "price": price})
    opening = buyer.opening()
    deal["chat"].append({"from": "buyer", "text": opening})
    conversations.append(party, "buyer", opening)
    emit("seller", "message", f"Buyer: {opening}", {"deal_id": deal["id"]})
    rounds = 0
    for _ in range(6):
        rounds += 1
        msg = f"It's ${price:,}, inspected and detailed. Can you do that?"
        deal["chat"].append({"from": "agent", "text": msg, "tactic": "step_down"})
        conversations.append(party, "agent", msg, tag=f"${price:,}")
        accepted, counter, text = buyer.step(price)
        if text:
            deal["chat"].append({"from": "buyer", "text": text})
            conversations.append(party, "buyer", text)
            emit("seller", "message", f"Buyer: {text}", {"deal_id": deal["id"], "counter": counter})
        if accepted:
            if not await _ask_sale(deal, price):
                emit("seller", "state", f"Not selling {deal['car']} at ${price:,}; the car stays listed", {"deal_id": deal["id"]})
                deal["state"] = "listed"
                return False
            deal["sold_for"], deal["state"] = price, "sold"
            gain = price - deal["bought_for"]
            emit("seller", "state", f"Sold {deal['car']} for ${price:,} ({'+' if gain >= 0 else '-'}${abs(gain):,})",
                 {"deal_id": deal["id"], "price": price})
            seller_agent.record_sale(deal, days=random.Random(deal["id"]).randint(9, 40), sold_for=price, source=deal["id"])
            mem = await memory_layer.consolidate("seller", party, deal["id"], {
                "closed": True, "price": price, "ask": deal["list_price"], "rounds": rounds,
                "tactic": "step_down", "segment": getattr(buyer, "persona", "buyer")})
            emit("seller", "write", f"Saved to memory: [{mem['status']}] {mem['artifact']}", {"deal_id": deal["id"], **mem})
            return True
        if counter is None:
            break  # buyer walked away; the car stays listed for the next buyer
        if price <= floor:  # already at the dealer's minimum profit: hold, don't chase the buyer lower
            emit("seller", "state", f"Buyer below your minimum profit (floor ${floor:,}); keeping {deal['car']} listed",
                 {"deal_id": deal["id"], "floor": floor})
            break
        price = int(max(counter, round(price - (price - counter) * 0.5, -1), floor))  # never below the floor
    deal["state"] = "listed"
    emit("seller", "state", f"{deal['car']} still listed at ${deal['list_price']:,}; no sale this round", {"deal_id": deal["id"]})
    return False


async def approve(deal_id: str, yes: bool, reason: str = "") -> bool:
    """Owner decision. Yes buys the car, lists it and sells it; no stops the deal. False if there is nothing to decide."""
    deal = DEALS.get(deal_id)
    if not deal or deal["state"] != "awaiting_approval":
        return False
    deal["turn"] = None
    if not yes:
        deal.update(state="dropped", drop_reason=reason or "owner declined")
        emit("owner", "state", f"Declined {deal['car']}", {"deal_id": deal_id})
        return True
    deal["bought_for"] = deal["offer"]
    deal["state"] = "bought"
    emit("buyer", "state", f"Bought {deal['car']} for ${deal['bought_for']:,}", {"deal_id": deal_id, "price": deal["bought_for"]})
    deal["list_price"] = max(int(deal.pop("_resale", 0) or round(deal["bought_for"] * 1.15, -1)), _sell_floor(deal))
    _spawn(deal)
    return True


def _spawn(deal: dict) -> None:
    t = asyncio.get_running_loop().create_task(_after_buy(deal))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _after_buy(deal: dict) -> None:
    """Logistics -> merchandiser -> seller, in the background so the buy desk keeps negotiating."""
    _cur.set(deal["id"])
    try:
        if deal["state"] in ("bought", "in_transit"):
            save()
            await ops.logistics(deal, emit)
            save()
        if deal["state"] == "delivered":
            await ops.merchandise(deal, emit)
            save()
        for _ in range(MAX_BUYERS):  # new buyers come in over the days the car sits on the lot
            if deal["state"] != "listed":
                break
            await asyncio.sleep(ops.DAY_SECS)
            if await _sell(deal, sim.make_buyer(_SC[deal["id"]])):
                break
            save()
    except Exception as e:
        emit("system", "error", f"{deal['id']} after-buy step failed: {type(e).__name__}", {"deal_id": deal["id"]})


def resume() -> int:
    """On startup: restart shipments and listings that were in flight when the backend stopped."""
    todo = [d for d in DEALS.values() if d["state"] in ("bought", "in_transit", "delivered", "listed") and d["id"] in _SC]
    for d in todo:
        emit("system", "state", f"Resumed {d['id']} after restart ({d['state']})", {"deal_id": d["id"]})
        _spawn(d)
    return len(todo)


async def _one(sc: dict, live_call: bool = False) -> bool:
    """One car from found to agreed. Several of these run side by side. False when it never became a deal."""
    listing = sc["listing"]
    comps = round(sc["seller"]["ask"] * random.Random(sc["id"]).uniform(1.05, 1.22), -2)
    # Ceiling = resale estimate - recon - dealer's minimum profit, capped by ask and buy limit.
    max_buy = min(sc["seller"]["ask"], dealer_profile.get()["buy_limit"], comps - seller_agent.RECON - seller_agent.min_profit())
    if max_buy <= 0:
        return False  # no profit possible at any price, not worth a deal row
    _state["n"] += 1
    deal_id = f"D-{200 + _state['n']}"
    _cur.set(deal_id)
    is_live = live_call  # one caller per shift is a person answering in the browser; the rest are simulated
    if is_live:
        _state["live_busy"] = True  # no second caller until this one has really phoned in
    deal = {"id": deal_id, "car": _title(listing), "location": listing.get("city", ""), "state": "sourced",
            "asking": sc["seller"]["ask"], "max_buy": round(max_buy), "listing_url": listing.get("url"),
            "photos": listing.get("photo_urls") or [],
            # Profit if we pay exactly the max: expected resale (same SELL_FACTOR and RECON as the sales desk) minus max and recon.
            "max_profit": round(round(comps * seller_agent.SELL_FACTOR, -1) - max_buy - seller_agent.RECON),
            "valuation": {"low": round(comps * 0.94), "mid": comps, "high": round(comps * 1.06), "citations": []},
            "chat": [], "live": is_live, "turn": None}
    DEALS[deal_id], _SC[deal_id] = deal, sc
    _phase("valuing", deal_id)
    emit("scout", "state", f"Found {deal['car']} in {deal['location']}, asking ${deal['asking']:,}", {"deal_id": deal_id})
    await _appraise(deal)
    deal["state"] = "appraised"
    await asyncio.sleep(0.3)
    deal["state"] = "negotiating"
    _phase("negotiating", deal_id)
    seller = live.LiveSeller(deal, sim.make_seller(sc), emit) if is_live else sim.make_seller(sc)
    if is_live:
        deal["turn"] = {"who": "system", "action": "call", "since": time.time()}
    try:
        r = await agents.negotiate({"id": deal_id, "ask": deal["asking"], "max_buy": max_buy, "seller_id": sc["seller"]["sid"],
                                    "car": deal["car"], "comps_mid": comps, "dealer": "Joe's Auto", "voice": is_live,
                                    "chat_sink": deal["chat"]},
                                   seller, emit=emit)
    finally:
        if is_live:
            _state["live_busy"] = False
            if getattr(seller, "called", False):
                _state["live_done"] = True  # the call happened; otherwise the next car gets the call
    deal["turn"] = None
    deal["chat"] = _chat(r)
    # Write-ahead: squeeze the chat into one artifact + status for the shared brain; raw chat stays private.
    mem = await memory_layer.consolidate("negotiator", f"seller:{sc['seller']['sid']}", deal_id, r, deal["car"])
    emit("negotiator", "write", f"Saved to memory: [{mem['status']}] {mem['artifact']}", {"deal_id": deal_id, **mem})
    if not r["closed"]:
        deal.update(state="dropped", drop_reason=r.get("dropped") or "no deal")
        save()
        return True
    deal["offer"] = int(r["price"])
    deal["_resale"] = (r.get("resale_quote") or {}).get("resale_price")
    deal["state"] = "awaiting_approval"
    deal["turn"] = {"who": "owner", "action": "approve", "since": time.time()}
    profit = (r.get("resale_quote") or {}).get("profit")
    clear = profit is not None and profit >= AUTO_PROFIT_X * seller_agent.min_profit()
    if clear or dealer_profile.get()["decision_mode"] != "dealer_decides":
        emit("negotiator", "state", f"Auto-approved {deal['car']} at ${deal['offer']:,}"
             + (f": profit ~${int(profit):,} clears your rule" if clear else ""), {"deal_id": deal_id, "auto": True})
        save()
        await approve(deal_id, True)
        return True
    _phase("waiting for owner", deal_id)
    emit("negotiator", "approval", f"{deal['car']}: agreed ${deal['offer']:,}, needs your OK"
         + (f" (profit ~${int(profit):,} is under your rule)" if profit is not None else ""), {"deal_id": deal_id})
    save()
    return True


LIBRARIAN_EVERY = 3
SCOUT_EVERY = 6  # fresh market scan after this many cars started


def _supply(first: bool) -> list[dict]:
    """A fresh batch of cars (scenarios) for the cars still to be found."""
    _state["seed"] += 1
    sc = sim.scenarios(_state["seed"], 16, shuffle=True)
    batch = sc["train"] + sc["heldout"]
    if os.getenv("DEMO_MODE", "0") == "1" and first:
        # demo: an affordable scam attempt shows up as the second car, not by luck
        pool = sim.scenarios(_state["seed"], 60, shuffle=True)
        scam = next((x for x in pool["train"] + pool["heldout"] if x["seller"]["persona"] == "scammer"
                     and x["seller"]["ask"] <= dealer_profile.get()["buy_limit"]), None)
        if scam:
            batch = [x for x in batch if x["id"] != scam["id"]]
            batch.insert(1, scam)
    real = craigslist.load()
    if real:  # real Craigslist listings replace the simulated ones; seller behaviour stays simulated
        start = (_state["seed"] - 1) * len(batch)
        batch = [craigslist.as_scenario(x, real[(start + i) % len(real)]) for i, x in enumerate(batch)]
    return batch


async def _pipeline(sc: dict, live_call: bool, done: list) -> None:
    """One car's buy side, as its own task. Never raises: one bad deal must not stop the shift."""
    try:
        if await _one(sc, live_call) is not False:
            done.append(1)
            if len(done) % LIBRARIAN_EVERY == 0:
                _active["librarian"] = "tidying memory"
                try:
                    librarian.run(emit)  # distil lessons and tidy memory every few deals
                finally:
                    _active.pop("librarian", None)
    except Exception as e:
        emit("system", "error", f"Deal skipped: {type(e).__name__}", {"deal_id": _cur.get()})
    finally:
        if _cur.get():
            _phase("idle", _cur.get())
        save()


LOT_CARS = 3  # cars already on the lot when the shift opens, so buyer offers start coming in within seconds


def _seed_lot() -> None:
    """Morning stock: cars already bought and listed. Buyers send offers on them from the first seconds, so the
    sell side runs next to the buy side. Each goes through the same _sell path as a car the team bought."""
    batch = sim.scenarios(_state["seed"] + 500, 12, shuffle=True)
    for sc in (batch["train"] + batch["heldout"])[:LOT_CARS]:
        ask = sc["seller"]["ask"]
        _state["n"] += 1
        deal_id = f"D-{200 + _state['n']}"
        paid = round(ask * random.Random(deal_id).uniform(0.6, 0.88), -2)
        deal = {"id": deal_id, "car": _title(sc["listing"]), "location": sc["listing"].get("city", ""), "state": "listed",
                "asking": ask, "max_buy": round(paid), "listing_url": sc["listing"].get("url"),
                "photos": sc["listing"].get("photo_urls") or [], "chat": [], "turn": None,
                "valuation": {"low": round(ask * 0.95), "mid": ask, "high": round(ask * 1.1), "citations": []},
                "bought_for": int(paid), "shipping": 0, "list_price": int(round(ask * 1.12, -1)), "on_lot": True}
        deal["listing"] = ops._template_listing(deal)
        DEALS[deal_id], _SC[deal_id] = deal, sc
        emit("seller", "state", f"On the lot from yesterday: {deal['car']}, listed at ${deal['list_price']:,}", {"deal_id": deal_id})
        _spawn(deal)


async def _workday() -> None:
    """The shift: scout, then keep PARALLEL cars in negotiation at once until the shop clock runs out."""
    try:
        _state["continuous"], _state["cap"] = False, 0
        _sim_prev.clear()
        _state["started"], _state["ended"] = time.time(), None
        end_at = _state["started"] + SHIFT_SECS
        emit("system", "state", f"Shift started: {SHIFT_HOURS} shop hours, up to {PARALLEL} cars at once", {})
        _seed_lot()
        queue: list[dict] = []
        pipes: set = set()
        done: list = []
        spawned, next_spawn, first = 0, 0.0, True
        while _state["running"] and time.time() < end_at:
            if len(pipes) < PARALLEL and time.time() >= next_spawn and _state["n"] < MAX_DEALS:
                if not queue or (spawned and spawned % SCOUT_EVERY == 0 and spawned != _state.get("_scouted")):
                    _state["_scouted"] = spawned
                    _active["scout"] = "scouting"
                    try:
                        await _scout()
                    except Exception as e:
                        emit("system", "error", f"Scout skipped: {type(e).__name__}", {})
                    finally:
                        _active.pop("scout", None)
                    if not queue:
                        queue = _supply(first)
                        first = False
                    continue
                live_call = (bool(_state["live"]) and not _state["live_done"] and not _state.get("live_busy")
                             and time.time() - _state["started"] >= 5)  # the phone rings a few seconds in
                t = asyncio.get_running_loop().create_task(_pipeline(queue.pop(0), live_call, done))
                pipes.add(t)
                t.add_done_callback(pipes.discard)
                spawned += 1
                next_spawn = time.time() + random.uniform(2, 5)  # cars arrive staggered, like a real morning
            await asyncio.sleep(0.5)
        emit("system", "state", f"Shop day over: {_state['n']} cars worked" + ("" if not pipes else f", {len(pipes)} still finishing"), {})
    finally:
        _state["running"] = False
        _state["ended"] = time.time()
        _active.pop("scout", None)


def start() -> bool:
    if _state["running"]:
        return False
    _state["running"] = True
    _state["live"], _state["live_done"], _state["live_busy"] = True, False, False
    _state["task"] = asyncio.get_running_loop().create_task(_workday())
    return True


def stop() -> None:
    _state["running"] = False
    _state["ended"] = time.time()


def public_deals() -> list[dict]:
    return [{k: v for k, v in d.items() if not k.startswith("_")} for d in reversed(list(DEALS.values()))]


def briefing() -> dict:
    ds = list(DEALS.values())
    sold = [d for d in ds if d["state"] == "sold"]
    profit = sum(d["sold_for"] - d["bought_for"] for d in sold)
    waiting = [d["id"] for d in ds if d["state"] == "awaiting_approval"]
    shipping = [d["id"] for d in ds if d["state"] in ("bought", "in_transit", "delivered")]
    listed = [d["id"] for d in ds if d["state"] == "listed"]
    scams = sum(1 for e in EVENTS if e["type"] == "blocked")
    text = (f"{len(ds)} deals worked, {len(sold)} sold for ${profit:,} profit, {len(shipping)} on the way, "
            f"{len(listed)} on the storefront, {scams} scam{'s' * (scams != 1)} blocked, {len(waiting)} waiting for your OK"
            + (f": {', '.join(waiting)}." if waiting else "."))
    return {"text": text, "deals": len(ds), "sold": len(sold), "profit": profit, "awaiting": waiting,
            "shipping": shipping, "listed": listed, "scams_blocked": scams,
            "brain": brain.stats()}
