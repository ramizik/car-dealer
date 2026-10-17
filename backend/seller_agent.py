"""Seller agent: answers the buyer's resale question before and after a buy.

quote(car, buy_price) -> {resale_price, days_to_sell, profit, days_source, verdict, reasons}

The buyer asks: how much can we sell it for, how many days, and how much profit? Every number here
comes from code and brain data, never from the LLM. Assumptions are named constants below and the
reply says which numbers were estimated.
"""
import brain


def usd(n: float) -> str:
    """$1,500 or -$3,310."""
    return f"{'-' if n < 0 else ''}${abs(n):,.0f}"

SELL_FACTOR = 0.97  # expected sale vs retail mid: listed near retail, some negotiation slack. Replace with sales data.
RECON = 800  # detailing and minor repairs per car until real recon data exists
DEFAULT_DAYS = 30  # used only when the brain has no sales history for this model
MIN_SALES_FOR_DAYS = 3  # below this, the default is used and labelled as such
MIN_PROFIT = 1500  # dollars the buyer must clear
MAX_DAYS = 45  # slower sellers than this are passed on


def model_key(car: dict) -> str:
    """Brain key for a make and model, e.g. 'toyota tacoma'. Uses car['make'] and car['model'] when given."""
    make, model = car.get("make", ""), car.get("model", "")
    if make and model:
        return f"{make} {model}".lower()
    return (car.get("car") or "unknown").split(" · ")[0].lower()


def days_to_sell(key: str) -> tuple[float, str]:
    """Median days from past sales in the brain, or the default when there is not enough history."""
    obs = brain.get("market", f"days_to_sell|{key}").get("obs", {}).get("days", {})
    if obs and obs.get("n", 0) >= MIN_SALES_FOR_DAYS:
        return obs["median"], f"median of {obs['n']} past sales"
    return DEFAULT_DAYS, "default, not enough sales history"


def quote(car: dict, buy_price: float) -> dict:
    retail = car.get("comps_mid") or car.get("retail_mid")
    if not retail:  # no market value yet: do not block the buy, say so
        return {"verdict": "unknown", "reasons": ["no market value yet, resale not priced"], "resale_price": None,
                "days_to_sell": None, "profit": None, "days_source": None}

    resale = round(retail * SELL_FACTOR, -1)
    profit = round(resale - buy_price - RECON)
    days, source = days_to_sell(model_key(car))

    reasons = []
    if profit < MIN_PROFIT:
        reasons.append(f"profit {usd(profit)} is under the {usd(MIN_PROFIT)} minimum")
    if days > MAX_DAYS:
        reasons.append(f"about {days:.0f} days to sell is over the {MAX_DAYS}-day limit")
    verdict = "pass" if reasons else "buy"
    return {"verdict": verdict, "reasons": reasons or ["clears profit and speed limits"],
            "resale_price": resale, "days_to_sell": days, "profit": profit, "days_source": source}


def record_sale(car: dict, days: float, sold_for: float, source: str) -> None:
    """Called when a car sells. Feeds the days-to-sell median that later quotes use."""
    key = model_key(car)
    brain.write("seller", "market", f"days_to_sell|{key}", "obs", float(days), attr="days", confidence=0.8, source=source)
    brain.write("seller", "market", f"sold_price|{key}", "obs", float(sold_for), attr="price", confidence=0.8, source=source)
