"""The shift: runs simulated deals end to end and keeps the state the dashboard reads.

Each deal: scout -> appraise -> negotiate -> owner approval -> logistics -> merchandise -> sale to a simulated buyer.
Continuous mode (max_deals=0) keeps working until stopped; the librarian compacts the brain every few deals.
State is saved to data/state.json, so a restarted backend picks up shipments and listings where they were.
Prices come from code and the sim, never the LLM.
"""
import asyncio
import json
import random
import time
from pathlib import Path

import agents
import conversations
import librarian
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
          "phase": "idle", "deal": None, "continuous": False}
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
        if deal["state"] in ("sourced", "appraised", "negotiating"):
            deal.update(state="dropped", drop_reason="backend restarted mid-negotiation")


_restore()


def emit(agent: str, type_: str, text: str, data: dict | None = None) -> None:
    data = data or {}
    EVENTS.append({"id": len(EVENTS) + 1, "ts": time.time(), "deal_id": data.get("deal_id"), "agent": agent,
                   "type": type_, "text": text, "data": data})


def _phase(phase: str, deal_id: str | None = None) -> None:
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
          "confidence": payload.get("confidence"), "deal_id": _state["deal"]})


brain.listeners.append(_on_brain)


def status() -> dict:
    return {k: _state[k] for k in ("running", "n", "cap", "started", "ended", "phase", "deal", "continuous")} | {
        "background": len(_tasks)}


def running() -> bool:
    return _state["running"]


def _title(l: dict) -> str:
    return f"{l.get('year', '')} {l.get('make', '')} {l.get('model', '')} · {int(l.get('miles') or 0) // 1000}k mi".strip()


def _chat(result: dict) -> list[dict]:
    out = []
    for t in result.get("transcript", []):
        if t["from"] not in ("agent", "seller") or not t.get("text"):
            continue
        out.append({k: v for k, v in {"from": t["from"], "text": t["text"], "tactic": t.get("tactic"),
                                      "channel": t.get("channel"), "recalled": t.get("recalled") or None}.items() if v})
    return out


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
    emit("scout", "state", f"Scanned market: {len(found)} live listings", {"count": len(found)})


async def _appraise(deal: dict) -> None:
    """Appraiser: You.com research (lite) -> Nano extracts a range; keeps the sim range if anything fails."""
    skills.load("buyer/kbb")
    key = f"value:{deal['car'].split(' · ')[0]}".lower()
    known = brain.recall(["market"], keys=[key], agent="appraiser")
    try:
        r = await youcom.research(f"Current used market value range in USD for a {deal['car']}?", "lite")
        if not r.get("content"):
            raise ValueError("no research")
        v = await llm.chat_json(APPRAISE_SYSTEM, r["content"][:4000], tier=tier_for("appraiser"))
        lo, mid, hi = (int(v.get(k) or 0) for k in ("low", "mid", "high"))
        if not (0 < lo <= mid <= hi) or abs(mid - deal["valuation"]["mid"]) > deal["valuation"]["mid"] * 0.6:
            raise ValueError("implausible")  # sim prices rule the deal; research must roughly agree
        deal["valuation"].update(low=lo, mid=mid, high=hi, issues=v.get("issues") or [])
        deal["valuation"]["citations"] = r.get("sources", [])[:4]
    except Exception:
        pass
    val = deal["valuation"]
    brain.write("appraiser", "market", key, "obs", {"low": val["low"], "mid": val["mid"], "high": val["high"]},
                source=(val["citations"][0]["url"] if val["citations"] else "comps"), confidence=0.6)
    emit("appraiser", "state", f"Valued {deal['car']} at ${int(val['mid']):,}" + (f" ({len(known)} past notes)" if known else ""),
         {"deal_id": deal["id"], "sources": len(val["citations"])})


async def _sell(deal: dict, buyer: sim.Buyer) -> None:
    """List at the resale quote, then step down toward the simulated buyer. A walk-away means a discounted sale.

    The buyer chat goes through the same memory layers as the buy side: private log, then one shared artifact."""
    price = int(deal["list_price"])
    party = f"buyer:{deal['id']}"
    emit("seller", "state", f"Listed {deal['car']} at ${price:,}", {"deal_id": deal["id"], "price": price})
    opening = buyer.opening()
    deal["chat"].append({"from": "buyer", "text": opening})
    conversations.append(party, "buyer", opening)
    emit("seller", "message", f"Buyer: {opening}", {"deal_id": deal["id"]})
    sold, rounds = None, 0
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
            sold = price
            break
        if counter is None:
            sold = buyer.last_offer  # buyer walked: take their last number rather than hold the car
            break
        price = max(counter, round(price - (price - counter) * 0.5, -1))
    deal["sold_for"] = int(sold if sold is not None else buyer.last_offer)
    deal["state"] = "sold"
    gain = deal["sold_for"] - deal["bought_for"]
    emit("seller", "state", f"Sold {deal['car']} for ${deal['sold_for']:,} ({'+' if gain >= 0 else '-'}${abs(gain):,})",
         {"deal_id": deal["id"], "price": deal["sold_for"]})
    seller_agent.record_sale(deal, days=random.Random(deal["id"]).randint(9, 40), sold_for=deal["sold_for"], source=deal["id"])
    mem = await memory_layer.consolidate("seller", party, deal["id"], {
        "closed": True, "price": deal["sold_for"], "ask": deal["list_price"], "rounds": rounds,
        "tactic": "step_down", "segment": getattr(buyer, "persona", "buyer")})
    emit("seller", "write", f"Saved to memory: [{mem['status']}] {mem['artifact']}", {"deal_id": deal["id"], **mem})


async def approve(deal_id: str, yes: bool, reason: str = "") -> bool:
    """Owner decision. Yes buys the car, lists it and sells it; no stops the deal. False if there is nothing to decide."""
    deal = DEALS.get(deal_id)
    if not deal or deal["state"] != "awaiting_approval":
        return False
    if not yes:
        deal.update(state="dropped", drop_reason=reason or "owner declined")
        emit("owner", "state", f"Declined {deal['car']}", {"deal_id": deal_id})
        return True
    deal["bought_for"] = deal["offer"]
    deal["state"] = "bought"
    emit("buyer", "state", f"Bought {deal['car']} for ${deal['bought_for']:,}", {"deal_id": deal_id, "price": deal["bought_for"]})
    deal["list_price"] = int(deal.pop("_resale", 0) or round(deal["bought_for"] * 1.15, -1))
    _spawn(deal)
    return True


def _spawn(deal: dict) -> None:
    t = asyncio.get_running_loop().create_task(_after_buy(deal))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _after_buy(deal: dict) -> None:
    """Logistics -> merchandiser -> seller, in the background so the buy desk keeps negotiating."""
    try:
        if deal["state"] in ("bought", "in_transit"):
            save()
            await ops.logistics(deal, emit)
            save()
        if deal["state"] == "delivered":
            await ops.merchandise(deal, emit)
            save()
        if deal["state"] == "listed":
            await asyncio.sleep(ops.DAY_SECS)  # a few simulated days on the lot before the first buyer calls
            await _sell(deal, sim.make_buyer(_SC[deal["id"]]))
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


async def _one(i: int, sc: dict) -> None:
    listing = sc["listing"]
    deal_id = f"D-{200 + i}"
    comps = round(sc["seller"]["ask"] * random.Random(sc["id"]).uniform(1.05, 1.22), -2)
    max_buy = sc["seller"]["ask"] * 1.0
    if max_buy > dealer_profile.get()["buy_limit"]:
        return False  # over the dealer's spend limit, not worth a deal row
    deal = {"id": deal_id, "car": _title(listing), "location": listing.get("city", ""), "state": "sourced",
            "asking": sc["seller"]["ask"], "max_buy": round(max_buy), "listing_url": listing.get("url"),
            "valuation": {"low": round(comps * 0.94), "mid": comps, "high": round(comps * 1.06), "citations": []}, "chat": []}
    DEALS[deal_id], _SC[deal_id] = deal, sc
    emit("scout", "state", f"Found {deal['car']} in {deal['location']}, asking ${deal['asking']:,}", {"deal_id": deal_id})
    _phase("valuing", deal_id)
    await _appraise(deal)
    deal["state"] = "appraised"
    await asyncio.sleep(0.3)
    deal["state"] = "negotiating"
    _phase("negotiating", deal_id)
    r = await agents.negotiate({"id": deal_id, "ask": deal["asking"], "max_buy": max_buy, "seller_id": sc["seller"]["sid"],
                                "car": deal["car"], "comps_mid": comps, "dealer": "Joe's Auto"},
                               sim.make_seller(sc), emit=emit)
    deal["chat"] = _chat(r)
    # Write-ahead: squeeze the chat into one artifact + status for the shared brain; raw chat stays private.
    mem = await memory_layer.consolidate("negotiator", f"seller:{sc['seller']['sid']}", deal_id, r, deal["car"])
    emit("negotiator", "write", f"Saved to memory: [{mem['status']}] {mem['artifact']}", {"deal_id": deal_id, **mem})
    if not r["closed"]:
        deal.update(state="dropped", drop_reason=r.get("dropped") or "no deal")
        save()
        return
    deal["offer"] = int(r["price"])
    deal["_resale"] = (r.get("resale_quote") or {}).get("resale_price")
    deal["state"] = "awaiting_approval"
    _phase("waiting for owner", deal_id)
    emit("negotiator", "approval", f"{deal['car']}: agreed ${deal['offer']:,}, needs your OK", {"deal_id": deal_id})
    save()
    if dealer_profile.get()["decision_mode"] != "dealer_decides":
        await approve(deal_id, True)


LIBRARIAN_EVERY = 3


async def _run(max_deals: int) -> None:
    """max_deals=0: continuous shift, fresh market scans and sellers until someone presses stop."""
    try:
        _state["continuous"] = max_deals == 0
        _state["cap"] = 0 if max_deals == 0 else _state["n"] + max_deals
        _state["started"], _state["ended"] = time.time(), None
        done_here = 0
        emit("system", "state", "Shift started" + (" (continuous, runs until you stop it)" if not max_deals else f" ({max_deals} deals)"), {})
        while _state["running"] and (not _state["cap"] or _state["n"] < _state["cap"]):
            _state["seed"] += 1
            _phase("scouting")
            try:
                await _scout()
            except Exception as e:
                emit("system", "error", f"Scout skipped: {type(e).__name__}", {})
            sc = sim.scenarios(_state["seed"], max(max_deals, LIBRARIAN_EVERY) * 4)
            for sc_i in (sc["train"] + sc["heldout"]):
                if not _state["running"] or (_state["cap"] and _state["n"] >= _state["cap"]):
                    break
                _phase("sourcing")
                try:
                    if await _one(_state["n"] + 1, sc_i) is not False:
                        _state["n"] += 1
                        done_here += 1
                        if done_here % LIBRARIAN_EVERY == 0:
                            _phase("tidying memory")
                            librarian.run(emit)  # distil lessons and tidy memory every few deals
                except Exception as e:  # one bad deal must not stop the shift
                    emit("system", "error", f"Deal skipped: {type(e).__name__}", {})
                save()
                await asyncio.sleep(0.5)
                if done_here and done_here % 10 == 0:
                    break  # long shift: rescan the market every ten deals
            await asyncio.sleep(1)  # never spin if a whole batch was over the spend limit
    finally:
        _state["running"] = False
        _state["ended"] = time.time()
        _phase("idle")


def start(max_deals: int = 5) -> bool:
    if _state["running"]:
        return False
    _state["running"] = True
    _state["task"] = asyncio.get_running_loop().create_task(_run(max_deals))
    return True


def stop() -> None:
    _state["running"] = False


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
