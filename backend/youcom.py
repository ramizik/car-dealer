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

listeners = []  # callables(kind, payload): "call" | "cache_hit" | "error"
STATS = {"calls": 0, "cache_hits": 0, "errors": 0, "latency_total": 0.0}

# Query templates that point Search at individual listing pages (1.D3).
QUERY_TEMPLATES = [
    "{year_from}-{year_to} {make} {model} for sale near {city} under ${max_price}",
    "{year_from}-{year_to} {make} {model} for sale {city} site:cars.com",
    "used {make} {model} {year_from}-{year_to} for sale {city} site:cargurus.com",
    "{make} {model} {year_from}-{year_to} for sale by owner {city} craigslist",
    "{year_from} {make} {model} for sale near {city} site:autotrader.com",
]
LISTING_DOMAINS = ("cars.com", "autotrader.com", "cargurus.com", "craigslist.org", "bringatrailer.com",
                   "carsandbids.com", "copart.com", "iaai.com", "carmax.com", "truecar.com", "edmunds.com")
LISTING_PATH = re.compile(r"/vehicledetail/|/cars-for-sale/vehicle/|listing|/vehicle/|/cto/d/|/ctd/d/|/auctions/|/lot/|/\d{6,}")


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
    u = (url or "").lower()
    return any(d in u for d in LISTING_DOMAINS) and bool(LISTING_PATH.search(u))


def scout_queries(profile: dict) -> list[str]:
    p = {"year_from": 2015, "year_to": 2022, "city": "Stockton CA", "max_price": 30000, **profile}
    return [t.format(**p) for t in QUERY_TEMPLATES]


async def find_listing_urls(profile: dict, limit: int = 8) -> list[dict]:
    """Run scout queries, keep individual listing pages. [{url, title, description}]."""
    seen, out = set(), []
    results = await asyncio.gather(*(search(q, count=10) for q in scout_queries(profile)))
    for rs in results:
        for r in rs:
            url = r.get("url", "")
            if url in seen or not is_listing_url(url):
                continue
            seen.add(url)
            out.append({"url": url, "title": r.get("title", ""), "description": r.get("description", "")})
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


def seed_listings() -> list[dict]:
    """Guaranteed fallback listings (1.D5)."""
    try:
        return json.loads(SEED_LISTINGS.read_text(encoding="utf-8"))
    except Exception:
        return []


def stats() -> dict:
    n = STATS["calls"]
    return {**STATS, "avg_latency": round(STATS["latency_total"] / n, 2) if n else None,
            "demo_mode": _demo(), "has_key": bool(_key())}
