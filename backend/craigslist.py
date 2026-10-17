"""Read-only Craigslist pull: one public search page per run, saved to JSON.

Reads the public search page only. No login, no messages to sellers, no purchases.
Run it by hand: python craigslist.py --max-price 15000   (add --q honda to narrow)
"""
import argparse
import html
import json
import re
import time
from pathlib import Path

import httpx

OUT = Path(__file__).parent / "data" / "craigslist_listings.json"
SEARCH = "https://stockton.craigslist.org/search/cta"  # cars & trucks, Stockton, CA
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

ROW = re.compile(r'<li class="cl-static-search-result" title="([^"]*)">\s*<a href="([^"]+)">(.*?)</a>', re.S)
PRICE = re.compile(r'class="price">\$([\d,]+)<')
LOCATION = re.compile(r'class="location">\s*(.*?)\s*</div>', re.S)
LD = re.compile(r'<script type="application/ld\+json" id="ld_searchpage_results"\s*>(.*?)</script>', re.S)
PHOTOS = 8

MAKES = {"acura": "acura", "audi": "audi", "bmw": "bmw", "buick": "buick", "cadillac": "cadillac",
         "chevrolet": "chevrolet", "chevy": "chevrolet", "chrysler": "chrysler", "dodge": "dodge", "ram": "dodge",
         "fiat": "fiat", "ford": "ford", "gmc": "gmc", "honda": "honda", "hyundai": "hyundai", "infiniti": "infiniti",
         "jeep": "jeep", "kia": "kia", "lexus": "lexus", "lincoln": "lincoln", "mazda": "mazda", "mercedes": "mercedes",
         "mini": "mini", "mitsubishi": "mitsubishi", "nissan": "nissan", "pontiac": "pontiac", "porsche": "porsche",
         "subaru": "subaru", "tesla": "tesla", "toyota": "toyota", "volkswagen": "volkswagen", "vw": "volkswagen",
         "volvo": "volvo", "mustang": "ford", "silverado": "chevrolet", "camry": "toyota", "civic": "honda",
         "accord": "honda", "corolla": "toyota", "tacoma": "toyota", "prius": "toyota"}


def _photos(page: str) -> list[list[str]]:
    """Photo URLs per result, same order as the rows. Empty lists when the JSON-LD block is missing."""
    m = LD.search(page)
    try:
        items = json.loads(m.group(1)).get("itemListElement", []) if m else []
    except Exception:
        return []
    return [[u for u in (it.get("item") or {}).get("image") or [] if isinstance(u, str)][:PHOTOS] for it in items]


def parse(page: str) -> list[dict]:
    """One dict per listing row on a Craigslist search page."""
    photos = _photos(page)
    out = []
    for i, (title, url, body) in enumerate(ROW.findall(page)):
        price = PRICE.search(body)
        loc = LOCATION.search(body)
        out.append({
            "title": html.unescape(title),
            "price": int(price.group(1).replace(",", "")) if price else None,
            "location": html.unescape(loc.group(1)) if loc else "",
            "url": url,
            "photo_urls": photos[i] if i < len(photos) else [],
        })
    return out


def fetch(max_price: int | None = None, query: str = "") -> list[dict]:
    params = {"postedToday": "0"}
    if max_price:
        params["max_price"] = str(max_price)
    if query:
        params["query"] = query
    # One request per run. Redirects are followed so the regional page loads.
    r = httpx.get(SEARCH, params=params, headers={"User-Agent": UA}, follow_redirects=True, timeout=25)
    r.raise_for_status()
    return parse(r.text)


def make_of(title: str) -> str:
    words = re.findall(r"[a-z]+", title.lower())
    return next((MAKES[w] for w in words if w in MAKES), words[0] if words else "")


def diverse(rows: list[dict]) -> list[dict]:
    """Round-robin across makes so one brand never fills a batch. Photo listings first within each make."""
    by_make: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda r: not r.get("photo_urls")):
        by_make.setdefault(make_of(r["title"]), []).append(r)
    queues = sorted(by_make.values(), key=len, reverse=True)
    out = []
    while any(queues):
        out += [q.pop(0) for q in queues if q]
    return out


def load() -> list[dict]:
    """Saved listings with a usable price, mixed across makes. Empty when no pull has run yet."""
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8")).get("listings", [])
    except Exception:
        return []
    return diverse([r for r in rows if r.get("price") and 1000 <= r["price"] <= 60000 and r.get("url")])


def as_scenario(sc: dict, row: dict) -> dict:
    """Keep the simulated seller's behaviour. Take the real listing, asking price, link and photos from Craigslist."""
    ask = int(row["price"])
    listing = {"title": row["title"], "city": row["location"] or "Stockton, CA", "url": row["url"],
               "photo_urls": row.get("photo_urls") or [],
               "price": ask, "seller_id": sc["listing"]["seller_id"], "source": "craigslist"}
    seller = {**sc["seller"], "ask": ask, "floor": min(sc["seller"]["floor"], round(ask * 0.85 / 50) * 50)}
    return {**sc, "listing": listing, "seller": seller}


def save(rows: list[dict], max_price: int | None, query: str) -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {"fetched_at": time.time(), "source": "craigslist", "query": query, "max_price": max_price,
           "count": len(rows), "listings": rows}
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=int, default=15000)
    ap.add_argument("--q", default="", help="keyword, e.g. honda (empty = all makes)")
    a = ap.parse_args()
    rows = fetch(a.max_price, a.q)
    path = save(rows, a.max_price, a.q)
    print(f"{len(rows)} listings, {sum(bool(r['photo_urls']) for r in rows)} with photos -> {path}")
