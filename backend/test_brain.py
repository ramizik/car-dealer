"""Brain checks. Run: cd backend && python test_brain.py (plain asserts, no pytest)."""
import random
import tempfile
from pathlib import Path

import brain

# isolate from real data
tmp = Path(tempfile.mkdtemp())
brain.DIR, brain.LOG, brain.SNAPSHOTS = tmp, tmp / "events.jsonl", tmp / "snapshots"
brain.reset()


def rand_events(n, seed=0):
    r = random.Random(seed)
    evs = []
    for i in range(n):
        scope = r.choice(brain.SCOPES)
        kind = r.choice(brain.KINDS)
        key = f"{scope}-k{r.randint(0, 6)}"
        value = {
            "fact": r.choice(["a", "b", "c", 1, 2]),
            "obs": r.randint(10000, 30000),
            "counter": r.choice([1, {"tries": 1, "wins": r.randint(0, 1)}]),
            "note": r.choice(["Wants cash", "wants  CASH!", "Moving to Reno", "two owners", "rebuilt title"]),
        }[kind]
        evs.append({"ts": 1_760_000_000 + r.randint(0, 40) * 3600, "agent": "t", "scope": scope, "key": key,
                    "kind": kind, "attr": r.choice([None, "x", "y"]), "value": value, "source": "",
                    "confidence": r.choice([0.3, 0.5, 0.7, 0.9])})
    return evs


# 1. bad scope / kind raise at once
for bad in [dict(scope="nope", kind="fact"), dict(scope="dealer", kind="nope")]:
    try:
        brain.write("t", key="k", value=1, **bad)
        raise AssertionError("should raise")
    except ValueError:
        pass

# 2. order independence: 200 events shuffled 20 times -> identical view
evs = rand_events(200)
base = brain.view(evs)
for i in range(20):
    random.Random(i).shuffle(evs)
    assert brain.view(evs) == base, f"view changed on shuffle {i}"
assert base["conflicts"], "expected at least one conflict in random data"

# 3. merge rules
brain.write("a", "playbook", "fast_cash_pickup|motivated_private", "counter", {"tries": 1, "wins": 1})
brain.write("b", "playbook", "fast_cash_pickup|motivated_private", "counter", {"tries": 1, "wins": 0})
brain.write("a", "dealer", "joes-auto", "fact", 110000, attr="max_mileage", confidence=1.0)
brain.write("b", "dealer", "joes-auto", "fact", 90000, attr="max_mileage", confidence=0.8)
for p in (24000, 24100, 25000):
    brain.write("a", "market", "toyota-tacoma-2019-trd", "obs", p, attr="private_value", source="https://x")
brain.write("n", "party", "seller:S-07", "note", "Moving to Reno on the 25th")
brain.write("n", "party", "seller:S-07", "note", "moving to reno on the 25th!")
v = brain.view()
assert v["scopes"]["playbook"]["fast_cash_pickup|motivated_private"]["counters"]["_"] == {"tries": 2, "wins": 1}
assert v["scopes"]["dealer"]["joes-auto"]["facts"]["max_mileage"]["value"] == 110000
assert len(v["conflicts"]) == 1
assert v["scopes"]["market"]["toyota-tacoma-2019-trd"]["obs"]["private_value"]["median"] == 24100
assert len(v["scopes"]["party"]["seller:S-07"]["notes"]) == 1

# 4. recall: readable lines, exact key first, budget respected, emits event
seen = []
brain.listeners.append(lambda agent, kind, p: seen.append(kind))
lines = brain.recall(["playbook", "party"], keys=["fast_cash_pickup|motivated_private", "seller:"], agent="negotiator")
assert lines[0] == "playbook: fast_cash_pickup @ motivated_private wins 1/2", lines
assert any("reno" in l.lower() for l in lines)
assert len("\n".join(brain.recall(brain.SCOPES, budget_chars=60))) <= 60
assert "recall" in seen

# 5. ENABLED off: recall empty, write no-op
brain.ENABLED = False
n = brain.stats()["events"]
assert brain.recall(brain.SCOPES) == [] and brain.write("a", "dealer", "k", "fact", 1) is None
assert brain.stats()["events"] == n
brain.ENABLED = True

# 6. snapshot round trip + stats
brain.snapshot("warm")
brain.reset()
assert brain.stats()["events"] == 0
assert brain.load("warm") == n
st = brain.stats()
assert st["events"] == n and st["conflicts"] == 1 and st["bytes"] > 0
assert brain.playbook()[0]["rate"] == 0.5

print(f"brain ok: {n} events, view stable over 20 shuffles, stats={st}")
