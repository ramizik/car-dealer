"""P4 eval: shared brain OFF vs ON on held-out sellers.

Protocol: reset brain, train 20 scenarios x EVAL_EPOCHS (default 10) brain ON (epsilon=0.15), snapshot `warm`,
then held-out 10 with brain OFF and with brain ON (epsilon=0). Fully offline:
SIM_FAST=1 templated seller text, keyword segment classifier, template agent text.

Run: cd backend && SIM_FAST=1 python eval.py
"""
import asyncio
import json
import os
import random
import time
from pathlib import Path

os.environ.setdefault("SIM_FAST", "1")
os.environ["AGENT_TEXT"] = "0"

import llm  # noqa: E402

llm._client = None  # mock mode: deterministic, no API calls

import agents  # noqa: E402
import brain  # noqa: E402
import sim  # noqa: E402

OUT = Path(__file__).parent / "data" / "eval_result.json"
SEED = int(os.getenv("EVAL_SEED", "1"))
EPOCHS = int(os.getenv("EVAL_EPOCHS", "10"))


def _deal(sc: dict) -> dict:
    s = sc["seller"]
    return {"id": sc["id"], "ask": s["ask"], "max_buy": round(s["ask"] * 0.95), "seller_id": s["sid"],
            "car": sc["listing"].get("title", ""), "listing": sc["listing"]}


async def _run(scs: list[dict], epsilon: float, tag: str = "") -> list[dict]:
    rows = []
    for sc in scs:
        rng = random.Random(f"eval-{tag}{sc['id']}")
        r = await agents.negotiate(_deal(sc), sim.make_seller(sc), epsilon=epsilon, rng=rng)
        scam = sc["seller"]["persona"] == "scammer"
        rows.append({"id": sc["id"], "persona": sc["seller"]["persona"], "segment": r["segment"],
                     "tactic": r["tactic"], "closed": r["closed"], "price": r["price"], "ask": r["ask"],
                     "floor": sc["seller"]["floor"], "rounds": r["rounds"], "dropped": r["dropped"],
                     "scam": scam, "correct": (not r["closed"]) if scam else r["closed"]})
    return rows


def _metrics(rows: list[dict]) -> dict:
    legit = [r for r in rows if not r["scam"]]
    closed = [r for r in legit if r["closed"]]
    saved = [(r["ask"] - r["price"]) / r["ask"] for r in closed]
    surplus = [(r["ask"] - r["price"]) / max(1, r["ask"] - r["floor"]) for r in closed]
    scams = [r for r in rows if r["scam"]]
    return {
        "n": len(rows),
        "closed": len(closed), "legit": len(legit),
        "close_rate": round(len(closed) / max(1, len(legit)), 3),
        "mean_saved_pct": round(100 * sum(saved) / max(1, len(saved)), 2),
        "surplus_captured_pct": round(100 * sum(surplus) / max(1, len(surplus)), 1),
        "mean_rounds": round(sum(r["rounds"] for r in closed) / max(1, len(closed)), 2),
        "scams_blocked": sum(not r["closed"] for r in scams), "scams": len(scams),
        "correct": sum(r["correct"] for r in rows),
    }


async def main() -> dict:
    t0 = time.time()
    split = sim.scenarios(SEED, 30)

    brain.ENABLED = False
    off = await _run(split["heldout"], 0.0)

    brain.ENABLED = True
    brain.snapshot("_pre_eval")  # keep the live brain; restored below
    try:
        brain.reset()
        train = []
        for e in range(EPOCHS):  # replay the train sellers; held-out never seen
            train = await _run(split["train"], 0.15, f"e{e}-")
        brain.snapshot("warm")
        on = await _run(split["heldout"], 0.0)
        book = brain.playbook()
    finally:
        brain.load("_pre_eval")

    res = {"seed": SEED, "train_n": len(train), "heldout_n": len(on),
           "off": _metrics(off), "on": _metrics(on), "train": _metrics(train),
           "playbook": book, "rows": {"off": off, "on": on},
           "secs": round(time.time() - t0, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2))

    print(f"{'metric':<22}{'OFF':>10}{'ON':>10}")
    for k in ("close_rate", "mean_saved_pct", "surplus_captured_pct", "mean_rounds", "scams_blocked", "correct"):
        print(f"{k:<22}{res['off'][k]:>10}{res['on'][k]:>10}")
    print("\nheld-out tactic per deal (OFF -> ON):")
    for a, b in zip(off, on):
        print(f"  {a['id']:<8}{a['persona']:<19}{a['tactic']:<20}-> {b['tactic']:<20}"
              f"{'closed' if a['closed'] else '-':>7} -> {'closed' if b['closed'] else '-'}")
    if os.getenv("EVAL_VERBOSE"):
        for p in book:
            print(f"  {p['segment']:<19}{p['tactic']:<20}tries={p['tries']} wins={p['wins']} saved={p['saved']}")
    print(f"\nwrote {OUT} in {res['secs']}s")
    return res


if __name__ == "__main__":
    asyncio.run(main())
