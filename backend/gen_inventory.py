"""Generate synthetic used-car inventory for demo. Deterministic per seed.

Every row carries "synthetic": true. Fake VINs (SYN prefix, valid check digit), no real URLs.
Run: python gen_inventory.py [--n 200] [--seed 7]  -> data/synthetic_inventory.json
"""
import argparse
import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "data" / "synthetic_inventory.json"
CURRENT_YEAR = 2026
CITIES = ["Stockton, CA", "Lodi, CA", "Modesto, CA", "Manteca, CA", "Tracy, CA"]
# make, model, base new price, trims
CATALOG = [
    ("Toyota", "Tacoma", 36000, ["SR", "SR5", "TRD Sport", "TRD Off Road"]),
    ("Toyota", "4Runner", 42000, ["SR5", "TRD Off Road", "Limited"]),
    ("Toyota", "RAV4", 32000, ["LE", "XLE", "Adventure"]),
    ("Toyota", "Camry", 30000, ["LE", "SE", "XSE"]),
    ("Toyota", "Corolla", 24000, ["LE", "SE", "XSE"]),
    ("Toyota", "Tundra", 48000, ["SR5", "Limited", "TRD Pro"]),
    ("Honda", "CR-V", 33000, ["LX", "EX", "EX-L"]),
    ("Honda", "Civic", 25000, ["LX", "Sport", "EX-L"]),
    ("Honda", "Accord", 30000, ["LX", "Sport", "EX-L"]),
    ("Ford", "F-150", 45000, ["XL", "XLT", "Lariat"]),
    ("Ford", "Escape", 31000, ["S", "SE", "Titanium"]),
    ("Ford", "Explorer", 42000, ["XLT", "ST-Line", "Limited"]),
    ("Chevrolet", "Silverado 1500", 45000, ["WT", "LT", "RST"]),
    ("Chevrolet", "Equinox", 30000, ["LS", "LT", "Premier"]),
    ("Nissan", "Rogue", 30000, ["S", "SV", "SL"]),
    ("Nissan", "Altima", 27000, ["S", "SV", "SR"]),
    ("Hyundai", "Tucson", 30000, ["SE", "SEL", "Limited"]),
    ("Subaru", "Outback", 33000, ["Base", "Premium", "Limited"]),
]
VIN_ALPHA = "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O, Q
TRANS = {**{str(d): d for d in range(10)}, **{c: v for c, v in zip(
    "ABCDEFGH" "JKLMN" "PR" "STUVWXYZ",
    [1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 7, 9, 2, 3, 4, 5, 6, 7, 8, 9])}}
WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def make_vin(rng: random.Random) -> str:
    body = "SYN" + "".join(rng.choice(VIN_ALPHA + "0123456789") for _ in range(14))
    total = sum(TRANS[c] * w for c, w in zip(body, WEIGHTS))  # body[8] has weight 0, ignored
    check = total % 11
    return body[:8] + ("X" if check == 10 else str(check)) + body[9:]


def make_row(rng: random.Random) -> dict:
    make, model, base, trims = rng.choice(CATALOG)
    year = rng.randint(CURRENT_YEAR - 14, CURRENT_YEAR - 1)
    age = CURRENT_YEAR - year
    miles = max(500, int(age * rng.uniform(9000, 15000)))
    # ~12%/yr depreciation, $0.05 off per mile above 12k/yr, +-8% noise
    price = base * (0.88 ** age) - 0.05 * max(0, miles - 12000 * age)
    price = round(price * rng.uniform(0.92, 1.08), -2)
    roll = rng.random()
    title = "clean" if roll < 0.92 else ("rebuilt" if roll < 0.97 else "salvage")
    return {
        "year": year, "make": make, "model": model, "trim": rng.choice(trims),
        "miles": miles, "price": max(1500, int(price)), "city": rng.choice(CITIES),
        "title_status": title, "owners": rng.randint(1, 3), "vin": make_vin(rng),
        "url": None, "photo_urls": [], "source": "synthetic (generated)", "synthetic": True,
    }


def generate(n: int = 200, seed: int = 7) -> list[dict]:
    rng = random.Random(f"synthetic-inventory-{seed}")
    return [make_row(rng) for _ in range(n)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rows = generate(a.n, a.seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} synthetic cars -> {OUT}")
