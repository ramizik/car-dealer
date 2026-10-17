"""You.com Search / Contents / Research with a disk cache. Never raises.

DEMO_MODE=1 reads only from data/cache (no network). No key -> cache only too.
Errors return an empty result and notify `listeners` with ("error", payload).
"""
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path

import httpx

SEARCH_URL = "https://ydc-index.io/v1/search"
CONTENTS_URL = "https://ydc-index.io/v1/contents"
RESEARCH_URL = "https://api.you.com/v1/research"

DATA = Path(__file__).parent / "data"
CACHE = DATA / "cache"
SEED_LISTINGS = DATA / "seed_listings.json"
SYNTHETIC_LISTINGS = DATA / "synthetic_inventory.json"  # gen_inventory.py, labeled synthetic

listeners = []  # callables(kind, payload): "call" | "cache_hit" | "error"
STATS = {"calls": 0, "cache_hits": 0, "errors": 0, "latency_total": 0.0}

# Query templates (1.D3), tested live 2026-10-17 for Toyota Tacoma/4Runner/RAV4/Tundra near Stockton.
# Listing pages per 10 results: craigslist cto 2-6, certified-inventory 0-1. Aggregators (cars.com,
# cargurus, autotrader, truecar) only return search pages -> use extract_listings() on their markdown.
QUERY_TEMPLATES = [
    "site:{cl_site}.craigslist.org {make} {model} {city_short} cto",
    "certified used {make} {model} {city_short} inventory stock VIN price mileage",
    "{year_from}-{year_to} {make} {model} for sale near {city} under ${max_price}",
]
LISTING_URL = re.compile(
    r"craigslist\.org/.+/ct[od]/d/|/vehicledetail/|/cars-for-sale/vehicle/|bringatrailer\.com/listing/"
    r"|carsandbids\.com/auctions/|/inventory/.*[a-hj-npr-z0-9]{17}|/auto/used-.+/\d+")
AGGREGATORS = ("cars.com/shopping/", "cargurus.com/cars/", "autotrader.com/cars-for-sale/", "truecar.com/used-cars-for-sale/")


def _key() -> str:
    return os.getenv("YDC_API_KEY") or os.getenv("YOU_API_KEY") or ""


def _demo() -> bool:
    return os.getenv("DEMO_MODE", "0") == "1"


def _emit(kind: str, payload) -> None:
    for fn in listeners:
        try:
            fn(kind, payload)
        except Exception:
            pass


def _cache_path(endpoint: str, payload: dict) -> Path:
    h = hashlib.sha1((endpoint + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
    return CACHE / f"{h}.json"


async def _post(endpoint: str, payload: dict, timeout: float, empty):
    path = _cache_path(endpoint, payload)
    if path.exists():
        try:
            STATS["cache_hits"] += 1
            _emit("cache_hit", {"endpoint": endpoint})
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        except Exception:
            pass
    if _demo() or not _key():
        _emit("error", {"endpoint": endpoint, "error": "cache miss (demo mode or no key)"})
        return empty
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(endpoint, json=payload, headers={"X-API-Key": _key()})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        STATS["errors"] += 1
        _emit("error", {"endpoint": endpoint, "error": str(e)[:300]})
        return empty
    dt = time.monotonic() - t0
    STATS["calls"] += 1
    STATS["latency_total"] += dt
    _emit("call", {"endpoint": endpoint, "latency": round(dt, 2)})
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"endpoint": endpoint, "payload": payload, "response": data}), encoding="utf-8")
    except Exception:
        pass
    return data


async def search(query: str, count: int = 10, **extra) -> list[dict]:
    """Web results: [{url, title, description, snippets}]."""
    data = await _post(SEARCH_URL, {"query": query, "count": count, **extra}, 30, {})
    try:
        return list((data.get("results") or {}).get("web") or [])
    except Exception:
        return []


async def contents(urls: list[str]) -> list[dict]:
    """[{url, title, markdown}] - one per fetched page."""
    if not urls:
        return []
    data = await _post(CONTENTS_URL, {"urls": list(urls), "formats": ["markdown"]}, 30, [])
    return data if isinstance(data, list) else []


async def research(question: str, effort: str = "lite") -> dict:
    """{content, sources: [{url, title}]} - cited answer, {} on failure."""
    data = await _post(RESEARCH_URL, {"input": question, "research_effort": effort}, 90, {})
    if not isinstance(data, dict) or not data:
        return {}
    out = data.get("output") if isinstance(data.get("output"), dict) else data
    content = out.get("content") or out.get("answer") or out.get("text") or ""
    srcs = out.get("sources") or out.get("citations") or data.get("sources") or []
    sources = []
    for s in srcs:
        if isinstance(s, str):
            sources.append({"url": s, "title": ""})
        elif isinstance(s, dict) and s.get("url"):
            sources.append({"url": s["url"], "title": s.get("title", "")})
    return {"content": content if isinstance(content, str) else json.dumps(content), "sources": sources}


def is_listing_url(url: str) -> bool:
    return bool(LISTING_URL.search((url or "").lower()))


def is_aggregator_url(url: str) -> bool:
    return any(a in (url or "").lower() for a in AGGREGATORS)


def scout_queries(profile: dict) -> list[str]:
    p = {"year_from": 2015, "year_to": 2022, "city": "Stockton CA", "max_price": 30000, "cl_site": "sfbay", **profile}
    p.setdefault("city_short", p["city"].split(",")[0].split(" CA")[0])
    return [t.format(**p) for t in QUERY_TEMPLATES]


async def find_listing_urls(profile: dict, limit: int = 8) -> list[dict]:
    """Run scout queries, keep individual listing pages. [{url, title, description}].
    Aggregator search pages are kept at the end with kind="aggregator" for extract_listings()."""
    seen, out = set(), []
    results = await asyncio.gather(*(search(q, count=10) for q in scout_queries(profile)))
    for rs in results:
        for r in rs:
            url = r.get("url", "")
            if url in seen or not (is_listing_url(url) or is_aggregator_url(url)):
                continue
            seen.add(url)
            kind = "listing" if is_listing_url(url) else "aggregator"
            text = "\n".join([r.get("title", ""), r.get("description", "")] + list(r.get("snippets") or []))
            out.append({"url": url, "title": r.get("title", ""), "description": r.get("description", ""),
                        "kind": kind, "text": text})
    out.sort(key=lambda x: x["kind"] != "listing")
    return out[:limit]


EXTRACT_SYSTEM = (
    "Extract one used-car listing from the page. Return JSON with keys: year (int), make, model, trim, "
    "miles (int), price (int USD), city, title_status (clean|rebuilt|salvage|unknown), vin, url, photo_urls (list). "
    "Use null for unknown values. Never invent numbers."
)


def _int(v):
    try:
        return int(re.sub(r"[^\d]", "", str(v))) or None
    except Exception:
        return None


async def extract_listing(markdown: str, url: str = "") -> dict | None:
    """Nano extracts listing JSON; None if price or miles missing (1.D4)."""
    import llm
    if not markdown:
        return None
    d = await llm.chat_json(EXTRACT_SYSTEM, f"URL: {url}\n\n{markdown[:6000]}", tier="fast")
    if not isinstance(d, dict):
        return None
    d["price"], d["miles"], d["year"] = _int(d.get("price")), _int(d.get("miles")), _int(d.get("year"))
    if not d["price"] or not d["miles"]:
        return None
    d["url"] = d.get("url") or url
    d["photo_urls"] = d.get("photo_urls") or []
    return d


EXTRACT_MANY_SYSTEM = (
    "The page is a used-car search results page. Extract up to 10 individual listings as a JSON list. "
    "Each item: year (int), make, model, trim, miles (int), price (int USD), city, url (absolute if shown). "
    "Skip items without both price and miles. Never invent numbers."
)


async def extract_listings(markdown: str, url: str = "") -> list[dict]:
    """Many listings from one aggregator page (cars.com/cargurus search results)."""
    import llm
    if not markdown:
        return []
    d = await llm.chat_json(EXTRACT_MANY_SYSTEM, f"Page: {url}\n\n{markdown[:12000]}", tier="fast")
    items = d if isinstance(d, list) else (d.get("listings") or []) if isinstance(d, dict) else []
    out = []
    for x in items:
        if not isinstance(x, dict):
            continue
        x["price"], x["miles"], x["year"] = _int(x.get("price")), _int(x.get("miles")), _int(x.get("year"))
        if x["price"] and x["miles"]:
            x["url"] = x.get("url") or url
            x.setdefault("photo_urls", [])
            out.append(x)
    return out


async def fetch_listings(items: list[dict]) -> list[dict]:
    """find_listing_urls() output -> parsed listings. Contents API first; craigslist blocks it,
    so fall back to the search snippets (they carry year/miles/VIN). Aggregators -> many listings.
    Parsed result is cached too, so demo mode is instant and stable."""
    memo = _cache_path("parsed", {"urls": [i["url"] for i in items]})
    if memo.exists():
        try:
            return json.loads(memo.read_text(encoding="utf-8"))["response"]
        except Exception:
            pass
    pages = {p.get("url"): p.get("markdown") or "" for p in await contents([i["url"] for i in items])}
    out = []
    for i in items:
        md = pages.get(i["url"]) or ""
        if i.get("kind") == "aggregator":
            out += await extract_listings(md, i["url"]) if md else []
        else:
            d = await extract_listing(md or i.get("text", ""), i["url"])
            if d:
                out.append(d)
    if out:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            memo.write_text(json.dumps({"endpoint": "parsed", "response": out}), encoding="utf-8")
        except Exception:
            pass
    return out


PRICE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{4,6})\b")


def prices_in(results: list[dict], lo: int = 2000, hi: int = 150000) -> list[int]:
    """Dollar amounts in search titles/descriptions/snippets, kept within [lo, hi]."""
    text = " ".join(" ".join([r.get("title") or "", r.get("description") or "", *(r.get("snippets") or [])]) for r in results)
    return [v for v in (int(m.replace(",", "")) for m in PRICE.findall(text)) if lo <= v <= hi]


def _sources(results: list[dict], n: int = 4) -> list[dict]:
    return [{"url": r["url"], "title": r.get("title", "")} for r in results if r.get("url")][:n]


async def retail_comps(car: str, city: str = "Stockton CA") -> dict:
    """Dealer retail asks for this car: {median, n, prices, sources}. Empty dict if search gives no prices."""
    results = await search(f"used {car} for sale {city} price", count=10)
    prices = prices_in(results)
    if not prices:
        return {}
    prices.sort()
    return {"median": prices[len(prices) // 2], "n": len(prices), "prices": prices[:10], "sources": _sources(results)}


async def market_value(car: str) -> dict:
    """Cited valuation question for the appraiser: Research first, search snippets as the fallback."""
    r = await research(f"Current used market value range in USD for a {car}? Include common issues to check.", "lite")
    if r.get("content"):
        return r
    results = await search(f"{car} private party value KBB Edmunds", count=8)
    text = "\n".join(" ".join([x.get("title", ""), x.get("description", ""), *(x.get("snippets") or [])]) for x in results)
    return {"content": text, "sources": _sources(results)} if text.strip() else {}


RISK_WORDS = ("stolen", "scam", "fraud", "salvage", "flood", "odometer", "rollback", "lemon", "recall")


async def risk_check(listing: dict) -> dict:
    """Web check on the VIN for stolen/salvage/flood/scam reports that mention that exact VIN. {flags, sources}.
    No VIN -> no search (a model-level "scam" query flags every car)."""
    vin = (listing.get("vin") or "").strip().upper()
    if len(vin) != 17:
        return {"flags": [], "sources": []}
    q = f'"{vin}" stolen OR salvage OR scam OR flood'
    results = await search(q, count=5)
    hits = [r for r in results if vin.lower() in json.dumps(r).lower()]
    text = lambda r: (r.get("title", "") + " " + r.get("description", "")).lower()
    hits = [r for r in hits if any(w in text(r) for w in RISK_WORDS)]
    flags = sorted({w for r in hits for w in RISK_WORDS if w in text(r)})
    return {"flags": flags, "sources": _sources(hits, 3), "query": q}


async def ask(question: str, effort: str = "lite") -> dict:
    """Free-form cited answer for the concierge (POST /research)."""
    r = await research(question[:500], effort if effort in ("lite", "standard") else "lite")
    if r.get("content"):
        return r
    results = await search(question[:300], count=5)
    return {"content": "\n".join(f"- {x.get('title', '')}: {x.get('description', '')}" for x in results),
            "sources": _sources(results), "fallback": "search"} if results else {"content": "", "sources": []}


def seed_listings() -> list[dict]:
    """Guaranteed fallback listings (1.D5): seed rows plus synthetic inventory when generated."""
    rows = []
    for path in (SEED_LISTINGS, SYNTHETIC_LISTINGS):
        try:
            rows += json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return rows


def stats() -> dict:
    n = STATS["calls"]
    return {**STATS, "avg_latency": round(STATS["latency_total"] / n, 2) if n else None,
            "demo_mode": _demo(), "has_key": bool(_key())}


DEMO_PROFILES = [{"make": "Toyota", "model": m, "city": "Stockton CA"} for m in ("Tacoma", "4Runner", "RAV4", "Tundra")]


async def prewarm(profiles: list[dict] = DEMO_PROFILES) -> dict:
    """Fill data/cache for the demo queries so DEMO_MODE=1 runs offline (3.D1)."""
    counts = {}
    for p in profiles:
        items = await find_listing_urls(p)
        counts[p["model"]] = len(await fetch_listings(items))
    return counts


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print(asyncio.run(prewarm()), stats())
