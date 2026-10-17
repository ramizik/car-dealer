"""After-buy agents: logistics (ship it home) and merchandiser (write the listing).

Each recalls before work and writes after, like every other agent. Prices and costs come from code,
brain data or You.com results; the LLM only writes listing copy.
"""
import asyncio
import random
import re
import statistics

import brain
import llm
import skills
import youcom
from agent_tiers import tier_for

HOME = "Stockton, CA"
DAY_SECS = 3  # simulated clock: one transport day takes 3 seconds on stage
SHIP_LOCAL, SHIP_FAR = 250, 900  # fallback when search and brain have nothing: same metro vs out of area
MARKUP = 0.0  # list at the resale quote; the sales desk already priced in slack


def _city_key(city: str) -> str:
    return re.sub(r"[^a-z]+", "-", (city or "unknown").lower()).strip("-")


def _prices(results: list[dict]) -> list[int]:
    text = " ".join(" ".join([r.get("description") or "", *(r.get("snippets") or [])]) for r in results)
    return [int(p.replace(",", "")) for p in re.findall(r"\$\s?(\d{1,2},?\d{3}|\d{3})\b", text)
            if 100 <= int(p.replace(",", "")) <= 3000]


async def logistics(deal: dict, emit) -> None:
    """Quote transport from the seller's city, book it, and move the deal along a simulated clock."""
    origin = deal.get("location") or HOME
    key = f"shipping|{_city_key(origin)}"
    known = brain.get("market", key).get("obs", {}).get("usd", {})
    brain.recall(["market"], keys=[key], agent="logistics")
    if known:
        cost, source = round(known["median"], -1), f"brain: median of {known['n']} past moves"
    else:
        results = await youcom.search(f"car transport cost {origin} to {HOME}", count=5)
        prices = _prices(results)
        if prices:
            cost, source = round(statistics.median(prices), -1), (results[0].get("url") or "you.com")
        else:
            local = "stockton" in origin.lower() or origin.lower().endswith(("ca", "california"))
            cost, source = (SHIP_LOCAL if local else SHIP_FAR), "estimate"
    brain.write("logistics", "market", key, "obs", float(cost), attr="usd", confidence=0.6, source=source)
    days = 1 if "stockton" in origin.lower() else random.Random(deal["id"]).randint(2, 3)
    deal.update(state="in_transit", shipping=int(cost), ship_days=days)
    leg = f"local pickup in {origin}" if "stockton" in origin.lower() else f"transport {origin} -> {HOME}"
    emit("logistics", "state", f"Booked {leg}: ${int(cost):,}, {days} day{'s' * (days > 1)} ({source.split(':')[0]})",
         {"deal_id": deal["id"], "price": int(cost)})
    await asyncio.sleep(days * DAY_SECS)
    deal["state"] = "delivered"
    emit("logistics", "state", f"{deal['car']} delivered to the lot", {"deal_id": deal["id"]})


LISTING_SYSTEM = ("You write used-car listings for a small dealer's website. Return JSON "
                  '{"title": str, "description": str (2 sentences, honest, no prices), "bullets": [5 short strings]}. '
                  "Never invent features, accidents or service history beyond what you are given.")


def _template_listing(deal: dict) -> dict:
    car = deal["car"]
    return {"title": f"{car.split(' · ')[0]} - inspected and ready",
            "description": f"{car} from {deal.get('location') or 'a local owner'}, checked by our team and detailed. "
                           "Test drives welcome, financing on request.",
            "bullets": [car.split(" · ")[-1], "Clean title checked", "Detailed and inspected",
                        "Local trade-ins welcome", "Ask about financing"]}


async def merchandise(deal: dict, emit) -> None:
    """Price from comps and past sales, then have the smart tier write the storefront copy."""
    skill = skills.load("seller/listing")
    model = " ".join(w for w in deal["car"].split(" · ")[0].split() if not re.fullmatch(r"\d{4}", w))[:40].lower()
    memory = brain.recall(["market", "dealer"], keys=[f"sold_price|{model}", f"days_to_sell|{model}"], agent="merchandiser")
    sold = brain.get("market", f"sold_price|{model}").get("obs", {}).get("price", {})
    price = int(deal.get("list_price") or 0) or round(deal["bought_for"] * 1.15, -1)
    if sold and sold.get("n", 0) >= 2:  # past sales of this model pull the sticker toward what actually sold
        price = round((price + sold["median"]) / 2, -1)
    price = int(max(price * (1 + MARKUP), deal["bought_for"] + deal.get("shipping", 0) + 500))
    copy = {}
    if llm._client is not None:
        copy = await llm.chat_json(LISTING_SYSTEM + "\n" + skill["text"][:1500],
                                   f"Car: {deal['car']}\nLocation bought: {deal.get('location')}\n"
                                   f"Known issues: {', '.join((deal.get('valuation') or {}).get('issues') or []) or 'none reported'}\n"
                                   f"What we know: {'; '.join(memory[:5])}", tier=tier_for("seller/listing"))
    if not isinstance(copy, dict) or not copy.get("title"):
        copy = _template_listing(deal)
    deal.update(list_price=price, state="listed",
                listing={"title": str(copy["title"])[:90], "description": str(copy.get("description", ""))[:400],
                         "bullets": [str(b)[:60] for b in (copy.get("bullets") or [])][:5]})
    brain.write("merchandiser", "market", f"listed|{model}", "counter", {"listed": 1}, attr="listings", source=deal["id"])
    emit("merchandiser", "state", f"Published {deal['listing']['title']} at ${price:,} on the storefront"
         + (f" (priced from {sold['n']} past sales)" if sold and sold.get("n", 0) >= 2 else ""),
         {"deal_id": deal["id"], "price": price})

