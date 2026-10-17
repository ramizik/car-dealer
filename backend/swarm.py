"""The shift: runs simulated deals end to end and keeps the state the dashboard reads.

Each deal: seller negotiation (agents.negotiate) -> owner approval -> listing -> sale to a simulated buyer.
Everything is in memory; /deals and /events serve it. Prices come from code and the sim, never the LLM.
"""
import asyncio
import random
import time

import agents
import brain
import llm
import skills
import youcom
from agent_tiers import tier_for
import dealer_profile
import dealer_memory
import seller_agent
import sim

DEALS: dict[str, dict] = {}
EVENTS: list[dict] = []
_SC: dict[str, dict] = {}  # deal id -> scenario (hidden buyer lives here)
_state = {"running": False, "task": None, "seed": 0, "n": 0, "cap": 0}


def emit(agent: str, type_: str, text: str, data: dict | None = None) -> None:
    data = data or {}
    EVENTS.append({"id": len(EVENTS) + 1, "ts": time.time(), "deal_id": data.get("deal_id"), "agent": agent,
                   "type": type_, "text": text, "data": data})


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
    """List at the resale quote, then step down toward the simulated buyer. A walk-away means a discounted sale."""
    price = int(deal["list_price"])
    emit("seller", "state", f"Listed {deal['car']} at ${price:,}", {"deal_id": deal["id"], "price": price})
    sold = None
    for _ in range(6):
        accepted, counter, _ = buyer.step(price)
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
    deal["state"] = "listed"
    await _sell(deal, sim.make_buyer(_SC[deal_id]))
    return True


async def _one(i: int, sc: dict) -> None:
    listing = sc["listing"]
    deal_id = f"D-{200 + i}"
    comps = round(sc["seller"]["ask"] * random.Random(sc["id"]).uniform(1.05, 1.22), -2)
    max_buy = sc["seller"]["ask"] * 1.0
    if max_buy > dealer_profile.get()["buy_limit"]:
        return False  # over the dealer's spend limit, not worth a deal row
    deal = {"id": deal_id, "car": _title(listing), "location": listing.get("city", ""), "state": "negotiating",
            "asking": sc["seller"]["ask"], "max_buy": round(max_buy), "listing_url": listing.get("url"),
            "valuation": {"low": round(comps * 0.94), "mid": comps, "high": round(comps * 1.06), "citations": []}, "chat": []}
    DEALS[deal_id], _SC[deal_id] = deal, sc
    emit("scout", "state", f"Found {deal['car']} in {deal['location']}, asking ${deal['asking']:,}", {"deal_id": deal_id})
    await _appraise(deal)
    r = await agents.negotiate({"id": deal_id, "ask": deal["asking"], "max_buy": max_buy, "seller_id": sc["seller"]["sid"],
                                "car": deal["car"], "comps_mid": comps, "dealer": "Joe's Auto"},
                               sim.make_seller(sc), emit=emit)
    deal["chat"] = _chat(r)
    if not r["closed"]:
        deal.update(state="dropped", drop_reason=r.get("dropped") or "no deal")
        return
    deal["offer"] = int(r["price"])
    deal["_resale"] = (r.get("resale_quote") or {}).get("resale_price")
    deal["state"] = "awaiting_approval"
    emit("negotiator", "approval", f"{deal['car']}: agreed ${deal['offer']:,}, needs your OK", {"deal_id": deal_id})
    if dealer_profile.get()["decision_mode"] != "dealer_decides":
        await approve(deal_id, True)


async def _run(max_deals: int) -> None:
    try:
        _state["seed"] += 1
        _state["cap"] = _state["n"] + max_deals
        try:
            await _scout()
        except Exception as e:
            emit("system", "error", f"Scout skipped: {type(e).__name__}", {})
        sc = sim.scenarios(_state["seed"], max_deals * 4)
        for sc_i in (sc["train"] + sc["heldout"]):
            if _state["n"] >= _state["cap"]:
                break
            if not _state["running"]:
                break
            try:
                if await _one(_state["n"] + 1, sc_i) is not False:
                    _state["n"] += 1
            except Exception as e:  # one bad deal must not stop the shift
                emit("system", "error", f"Deal skipped: {type(e).__name__}", {})
            await asyncio.sleep(0.5)
    finally:
        _state["running"] = False


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
    text = (f"{len(ds)} deals worked, {len(sold)} sold for ${profit:,} profit, "
            f"{len(waiting)} waiting for your OK.")
    return {"text": text, "deals": len(ds), "sold": len(sold), "profit": profit, "awaiting": waiting,
            "brain": brain.stats()}
