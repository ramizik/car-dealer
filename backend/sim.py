"""Simulated counterparties: sellers, buyers, owner. Deterministic for a seed.

INTEGRITY RULE: the persona -> weak_to tactic mapping lives ONLY here. Agents never import
WEAK_TO / RATE. They see the seller's text (with leaked hints) and must learn which tactic
works through the shared brain.

SIM_FAST=1 -> templated text (eval). Otherwise the `sim` tier rewrites the template; prices never change.
"""
import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

TACTICS = ("fast_cash_pickup", "comps_anchor", "split_difference", "volume_relationship", "walk_away_threat")
PERSONAS = ("motivated_private", "price_anchored", "haggler", "wholesaler_repeat", "scammer")

WEAK_TO = {  # hidden
    "motivated_private": "fast_cash_pickup",
    "price_anchored": "comps_anchor",
    "haggler": "split_difference",
    "wholesaler_repeat": "volume_relationship",
    "scammer": None,
}
RATE = {  # share of the gap to eff_floor given up per counter
    "motivated_private": 0.45,
    "price_anchored": 0.15,
    "haggler": 0.30,
    "wholesaler_repeat": 0.35,
    "scammer": 0.0,
}
WEAK_DISCOUNT = 0.94

HINTS = {  # leaked tells, picked by seed
    "motivated_private": ["Need it gone before I move next week.", "Honestly just want this done fast.",
                          "I'm relocating, it has to go this weekend."],
    "price_anchored": ["KBB says it's worth way more than that.", "I looked up comps, my price is fair.",
                       "Edmunds has it higher than my ask."],
    "haggler": ["Come on, meet me somewhere in the middle.", "I like to make a deal, but not that low.",
                "Everything's negotiable, but you gotta come up."],
    "wholesaler_repeat": ["I move a lot of units, I want repeat buyers.", "If this goes well I've got more coming.",
                          "Looking for a dealer I can send inventory to regularly."],
    "scammer": ["I'm out of state on deployment, my agent ships it.", "Only payment through the escrow link I send.",
                "Price is low because I need it gone today, no inspections."],
}
PAYMENT_LINK = "https://secure-escrow-payments.example/pay?id={sid}"

DATA = Path(__file__).parent / "data"
SEED_LISTINGS = DATA / "seed_listings.json"
SYNTHETIC_LISTINGS = DATA / "synthetic_inventory.json"  # gen_inventory.py, labeled synthetic


def _fast() -> bool:
    return os.getenv("SIM_FAST", "0") == "1"


async def _rewrite(template: str, role: str) -> str:
    """Natural-language rewrite via the sim tier; keeps every number. Falls back to the template."""
    if _fast():
        return template
    try:
        import llm
        out = await llm.chat(
            f"You are a {role} texting about a used car. Rewrite the message casually in 1-2 sentences. "
            "Keep every number and URL exactly as written. Do not add new prices.",
            template, temperature=0.7, tier="sim", max_tokens=200)
        nums = [t for t in template.replace(",", "").split() if t.strip("$.,!?").isdigit()]
        urls = re.findall(r"https?://\S+", template)
        if out and all(n.strip("$.,!?") in out.replace(",", "") for n in nums) and all(u in out for u in urls):
            return out.strip()
    except Exception:
        pass
    return template


@dataclass
class Seller:
    ask: int
    floor: int
    persona: str
    patience: int = 5
    seed: int = 0
    sid: str = ""
    round: int = 0
    last_counter: int = 0
    done: bool = False
    history: list = field(default_factory=list)

    def __post_init__(self):
        self._rng = random.Random(f"seller-{self.seed}-{self.sid}")
        self.last_counter = self.ask
        self.sid = self.sid or f"s{self.seed}"

    def opening(self) -> str:
        return f"Asking ${self.ask}. {self._rng.choice(HINTS[self.persona])}"

    def step(self, offer: int, tactic: str | None = None) -> tuple[bool, int | None, str]:
        """Deterministic rule (1.D7). Returns (accepted, counter_price, template_text)."""
        if self.done:
            return False, None, "This conversation is over."
        self.round += 1
        hint = self._rng.choice(HINTS[self.persona])
        if self.persona == "scammer":
            if self.round == 2:
                text = f"Send ${self.ask} deposit here first: {PAYMENT_LINK.format(sid=self.sid)}. {hint}"
            else:
                text = f"Price is ${self.ask}, firm. {hint}"
            if self.round >= self.patience:
                self.done = True
                text = "Forget it, I have other buyers."
            self.history.append((offer, tactic, None))
            return False, (None if self.done else self.ask), text
        eff_floor = round(self.floor * (WEAK_DISCOUNT if tactic and tactic == WEAK_TO[self.persona] else 1.0))
        if offer >= eff_floor:
            self.done = True
            self.history.append((offer, tactic, "accept"))
            return True, offer, f"Deal at ${offer}. When can you pick it up?"
        if self.round >= self.patience:
            self.done = True
            self.history.append((offer, tactic, "walk"))
            return False, None, f"We're too far apart at ${offer}. I'll sell it elsewhere."
        counter = round(max(eff_floor, self.last_counter - (self.last_counter - eff_floor) * RATE[self.persona]))
        counter = max(counter, offer + 1)
        self.last_counter = counter
        self.history.append((offer, tactic, counter))
        return False, counter, f"${offer} is too low. I can do ${counter}. {hint}"

    async def respond(self, offer: int, tactic: str | None = None) -> tuple[bool, int | None, str]:
        accepted, counter, text = self.step(offer, tactic)
        return accepted, counter, await _rewrite(text, "private car seller")

    def public(self) -> dict:
        """What agents may see. No floor, no persona."""
        return {"sid": self.sid, "ask": self.ask, "patience_left": max(0, self.patience - self.round)}


@dataclass
class Buyer:
    """Mirror of the seller for the selling side: hidden max price + persona."""
    max_price: int
    persona: str
    patience: int = 5
    seed: int = 0
    bid: str = ""
    round: int = 0
    last_offer: int = 0
    done: bool = False

    def __post_init__(self):
        self._rng = random.Random(f"buyer-{self.seed}-{self.bid}")
        self.last_offer = round(self.max_price * {"motivated_private": 0.92, "price_anchored": 0.82,
                                                   "haggler": 0.80, "wholesaler_repeat": 0.85,
                                                   "scammer": 1.10}[self.persona])
        self.bid = self.bid or f"b{self.seed}"

    def opening(self) -> str:
        return f"Interested. Would you take ${self.last_offer}? {self._rng.choice(HINTS[self.persona])}"

    def step(self, price: int, tactic: str | None = None) -> tuple[bool, int | None, str]:
        """Dealer quotes `price`. Returns (accepted, counter_offer, text)."""
        if self.done:
            return False, None, "This conversation is over."
        self.round += 1
        if self.persona == "scammer":
            self.done = self.round >= 2
            return False, None, (f"I'll send a cashier's check for ${price + 1500}, just refund the difference."
                                 if self.round == 1 else "My shipper will contact you.")
        eff_max = round(self.max_price / (WEAK_DISCOUNT if tactic and tactic == WEAK_TO[self.persona] else 1.0))
        if price <= eff_max:
            self.done = True
            return True, price, f"OK, ${price} works. When can I see it?"
        if self.round >= self.patience:
            self.done = True
            return False, None, f"${price} is out of my budget. I'll keep looking."
        offer = round(min(eff_max, self.last_offer + (eff_max - self.last_offer) * RATE[self.persona]))
        offer = min(offer, price - 1)
        self.last_offer = offer
        return False, offer, f"${price} is steep. I can do ${offer}. {self._rng.choice(HINTS[self.persona])}"

    async def respond(self, price: int, tactic: str | None = None) -> tuple[bool, int | None, str]:
        accepted, counter, text = self.step(price, tactic)
        return accepted, counter, await _rewrite(text, "used car buyer")


@dataclass
class Owner:
    """Dealer owner with hidden true preferences. Agents learn them via approve/reject in the brain."""
    seed: int = 0
    max_owners: int = 2
    reject_titles: tuple = ("rebuilt", "salvage")
    max_miles: int = 150_000
    likes: tuple = ("4x4", "4wd", "trd")

    def approve(self, c: dict) -> bool:
        if str(c.get("title_status", "clean")).lower() in self.reject_titles:
            return False
        if (c.get("owners") or 1) > self.max_owners:
            return False
        if (c.get("miles") or 0) > self.max_miles:
            return False
        return True

    def reason(self, c: dict) -> str:
        if str(c.get("title_status", "clean")).lower() in self.reject_titles:
            return f"No {c.get('title_status')} titles. Ever."
        if (c.get("owners") or 1) > self.max_owners:
            return f"{c.get('owners')} owners is too many, max {self.max_owners}."
        if (c.get("miles") or 0) > self.max_miles:
            return f"{c.get('miles')} miles is too many."
        trim = f"{c.get('trim', '')} {c.get('title', '')}".lower()
        return "Approved, love a 4x4." if any(k in trim for k in self.likes) else "Approved."


FALLBACK_LISTINGS = [  # synthetic, used only if seed_listings.json is missing
    {"year": 2018, "make": "Toyota", "model": "Tacoma", "trim": "TRD Off-Road 4x4", "miles": 78000, "price": 29500},
    {"year": 2017, "make": "Toyota", "model": "4Runner", "trim": "SR5 4WD", "miles": 92000, "price": 27900},
    {"year": 2019, "make": "Toyota", "model": "RAV4", "trim": "XLE", "miles": 54000, "price": 23800},
    {"year": 2016, "make": "Toyota", "model": "Tundra", "trim": "SR5 4x4", "miles": 110000, "price": 26500},
    {"year": 2020, "make": "Honda", "model": "CR-V", "trim": "EX", "miles": 41000, "price": 24900},
    {"year": 2015, "make": "Ford", "model": "F-150", "trim": "XLT 4x4", "miles": 124000, "price": 21500},
]


def _listings() -> list[dict]:
    ls = []
    for path in (SEED_LISTINGS, SYNTHETIC_LISTINGS):
        try:
            ls += json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return ls or FALLBACK_LISTINGS


def _scenario(i: int, seed: int, rng: random.Random, listings: list[dict], wholesaler_ids: list[str]) -> dict:
    listing = dict(listings[i % len(listings)])
    persona = "scammer" if i % 10 == 7 else PERSONAS[(i + seed) % 4]  # balanced, 1 scammer per 10
    ask = int(listing.get("price") or 25000)
    ask = round(ask * rng.uniform(0.95, 1.08) / 100) * 100
    floor = round(ask * rng.uniform(0.80, 0.90) / 50) * 50
    if persona == "wholesaler_repeat" and wholesaler_ids and rng.random() < 0.5:
        sid = rng.choice(wholesaler_ids)  # deliberate repeat seller
    else:
        sid = f"seller-{seed}-{i}"
        if persona == "wholesaler_repeat":
            wholesaler_ids.append(sid)
    return {
        "id": f"sc-{seed}-{i}",
        "listing": {**listing, "price": ask, "seller_id": sid},
        "seller": {"ask": ask, "floor": floor, "persona": persona,
                   "patience": rng.randint(4, 6), "seed": seed * 1000 + i, "sid": sid},
        "buyer": {"max_price": round(ask * rng.uniform(1.12, 1.25) / 100) * 100,
                  "persona": PERSONAS[rng.randrange(4)], "patience": rng.randint(4, 6),
                  "seed": seed * 1000 + i, "bid": f"buyer-{seed}-{i}"},
    }


def scenarios(seed: int = 1, n: int = 30) -> dict:
    """{train: [...], heldout: [...]}. First 2/3 train, rest held-out. Stable for a seed (1.D10).
    Only wholesaler_repeat sellers may appear in both splits."""
    rng = random.Random(f"scenarios-{seed}")
    listings, wholesalers = _listings(), []
    all_sc = [_scenario(i, seed, rng, listings, wholesalers) for i in range(n)]
    cut = round(n * 2 / 3)
    return {"train": all_sc[:cut], "heldout": all_sc[cut:]}


def make_seller(sc: dict) -> Seller:
    return Seller(**sc["seller"])


def make_buyer(sc: dict) -> Buyer:
    return Buyer(**sc["buyer"])


def _selfcheck() -> None:
    # hand case 1: weak tactic lowers floor 6% -> offer at 0.95*floor accepted
    s = Seller(ask=20000, floor=17000, persona="motivated_private", seed=1)
    assert s.step(16150, "fast_cash_pickup")[0] is True
    # hand case 2: same offer, wrong tactic -> counter between floor and ask
    s = Seller(ask=20000, floor=17000, persona="motivated_private", seed=1)
    ok, c, _ = s.step(16150, "comps_anchor")
    assert not ok and c == round(20000 - (20000 - 17000) * 0.45) == 18650
    # hand case 3: scammer never sells, sends link on round 2
    s = Seller(ask=9000, floor=5000, persona="scammer", seed=1, sid="x")
    s.step(9000)
    assert "secure-escrow" in s.step(9000)[2]
    # patience walk-away
    s = Seller(ask=20000, floor=18000, persona="price_anchored", patience=2, seed=1)
    s.step(10000)
    assert s.step(10000)[1] is None and s.done
    # determinism
    assert json.dumps(scenarios(1, 30)) == json.dumps(scenarios(1, 30))
    sc = scenarios(1, 30)
    tr = {x["seller"]["sid"]: x["seller"]["persona"] for x in sc["train"]}
    shared = [x for x in sc["heldout"] if x["seller"]["sid"] in tr]
    assert all(x["seller"]["persona"] == "wholesaler_repeat" for x in shared)
    print("sim ok:", len(sc["train"]), "train,", len(sc["heldout"]), "heldout,", len(shared), "repeat wholesalers")


if __name__ == "__main__":
    _selfcheck()
