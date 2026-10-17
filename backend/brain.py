"""Shared brain: append-only event log + pure reducer.

Every agent calls recall() before work and write() after. The log is the only
state; view() folds it with order-independent merge rules, so concurrent
writers never conflict (counters sum, obs take a median, facts resolve by
confidence then recency, notes dedupe).
"""
import json
import re
import shutil
import statistics
import threading
import time
from pathlib import Path

DIR = Path(__file__).parent / "data" / "brain"
LOG = DIR / "events.jsonl"
SNAPSHOTS = DIR / "snapshots"

SCOPES = ("dealer", "party", "market", "playbook")
KINDS = ("fact", "obs", "counter", "note")
OBS_CAP = 200
OBS_TTL = 30 * 86400
NOTE_CAP = {"party": 50, "dealer": 30}
NOTE_CAP_DEFAULT = 50
CONFLICT_CONF = 0.7

ENABLED = True
RECALL_STATS = {"calls": 0, "chars": 0}  # memory text handed to agents, for the admin page
listeners = []  # callables(agent, kind, payload) -> swarm turns these into feed events

_lock = threading.Lock()
_events: list[dict] = []
_loaded = False


def _emit(agent: str, kind: str, payload) -> None:
    for fn in listeners:
        try:
            fn(agent, kind, payload)
        except Exception:
            pass


def _load_log() -> None:
    global _loaded, _events
    if _loaded:
        return
    _events = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    _events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    _loaded = True


def events() -> list[dict]:
    with _lock:
        _load_log()
        return list(_events)


def write(agent, scope, key, kind, value, source="", confidence=0.5, attr=None, ts=None, visible_to=None) -> dict | None:
    """visible_to: agent names allowed to recall this write. None means every agent (shared)."""
    if scope not in SCOPES:
        raise ValueError(f"bad scope {scope!r}, want one of {SCOPES}")
    if kind not in KINDS:
        raise ValueError(f"bad kind {kind!r}, want one of {KINDS}")
    if not ENABLED:
        return None
    ev = {
        "ts": time.time() if ts is None else ts,
        "agent": agent, "scope": scope, "key": str(key), "kind": kind,
        "attr": attr, "value": value, "source": source, "confidence": float(confidence),
    }
    if visible_to:
        ev["visible_to"] = sorted(visible_to)
    with _lock:
        _load_log()
        DIR.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        _events.append(ev)
    _emit(agent, "write", ev)
    return ev


# ---------- reducer ----------

def _norm(text) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(text).lower())).strip()


def _order(ev) -> tuple:
    # total order independent of arrival order
    return (ev.get("ts", 0), json.dumps(ev, sort_keys=True, default=str))


def _add_counter(acc, value):
    if isinstance(value, dict):
        acc = acc if isinstance(acc, dict) else {}
        for k, v in value.items():
            acc[k] = acc.get(k, 0) + v
        return acc
    return (acc if isinstance(acc, (int, float)) else 0) + value


def view(evs: list[dict] | None = None) -> dict:
    """Pure fold of events -> {scopes: {scope: {key: entry}}, conflicts: [...]}."""
    evs = sorted(events() if evs is None else evs, key=_order)
    now = max((e.get("ts", 0) for e in evs), default=0)
    out = {s: {} for s in SCOPES}
    facts, obs, notes = {}, {}, {}

    for e in evs:
        s, k, kind, attr = e["scope"], e["key"], e["kind"], e.get("attr") or "_"
        entry = out[s].setdefault(k, {"facts": {}, "obs": {}, "counters": {}, "notes": [], "ts": 0})
        entry["ts"] = max(entry["ts"], e.get("ts", 0))
        if kind == "counter":
            entry["counters"][attr] = _add_counter(entry["counters"].get(attr), e["value"])
        elif kind == "fact":
            facts.setdefault((s, k, attr), []).append(e)
        elif kind == "obs":
            if now - e.get("ts", 0) <= OBS_TTL and isinstance(e["value"], (int, float)):
                obs.setdefault((s, k, attr), []).append(e)
        elif kind == "note":
            notes.setdefault((s, k), {})[_norm(e["value"])] = e  # later same text wins

    conflicts = []
    for (s, k, attr), fs in facts.items():
        best = max(fs, key=lambda e: (e["confidence"], _order(e)))
        out[s][k]["facts"][attr] = {"value": best["value"], "confidence": best["confidence"],
                                    "source": best.get("source", ""), "agent": best.get("agent", "")}
        strong = {json.dumps(e["value"], sort_keys=True, default=str) for e in fs if e["confidence"] >= CONFLICT_CONF}
        if len(strong) > 1:
            conflicts.append({"scope": s, "key": k, "attr": attr, "values": sorted(strong),
                              "chosen": best["value"]})

    for (s, k, attr), os_ in obs.items():
        vals = [e["value"] for e in os_[-OBS_CAP:]]
        out[s][k]["obs"][attr] = {"median": statistics.median(vals), "n": len(vals),
                                  "sources": sorted({e.get("source", "") for e in os_ if e.get("source")})[:5]}

    for (s, k), by_text in notes.items():
        cap = NOTE_CAP.get(s, NOTE_CAP_DEFAULT)
        kept = sorted(by_text.values(), key=_order)[-cap:]
        out[s][k]["notes"] = [{"text": e["value"], "confidence": e["confidence"], "agent": e.get("agent", "")}
                              | ({"private_to": e["visible_to"]} if e.get("visible_to") else {}) for e in kept]

    conflicts.sort(key=lambda c: (c["scope"], c["key"], c["attr"]))
    return {"scopes": out, "conflicts": conflicts}


# ---------- recall ----------

def _fmt_num(v):
    return f"${v:,.0f}" if isinstance(v, (int, float)) and abs(v) >= 1000 else (f"{v:g}" if isinstance(v, float) else str(v))


def _lines(scope, key, entry):
    """Yield (confidence, line) for one brain entry."""
    for attr, f in entry["facts"].items():
        yield f["confidence"], f"{scope} {key}: {attr} = {_fmt_num(f['value'])}"
    for attr, o in entry["obs"].items():
        yield 0.6, f"{scope} {key}: {attr} median {_fmt_num(o['median'])} (n={o['n']})"
    for attr, c in entry["counters"].items():
        if isinstance(c, dict) and "tries" in c:
            label = key.replace("|", " @ ")
            yield 0.8, f"{scope}: {label} wins {c.get('wins', 0)}/{c['tries']}"
        else:
            yield 0.5, f"{scope} {key}: {attr} = {c}"
    for n in reversed(entry["notes"]):
        yield n["confidence"], f"{scope} {key}: {n['text']}"


def _visible(ev: dict, agent: str) -> bool:
    return not ev.get("visible_to") or agent in ev["visible_to"]


def recall(scopes, keys=(), tags=None, budget_chars=1500, agent="") -> list[str]:
    """Ranked one-line memories: exact key match, then partial match, then confidence, then recency."""
    if not ENABLED:
        return []
    scopes = [scopes] if isinstance(scopes, str) else list(scopes)
    keys = [keys] if isinstance(keys, str) else list(keys or [])
    tags = [t.lower() for t in (tags or [])]
    v = view([e for e in events() if _visible(e, agent)])["scopes"]  # private writes stay with their agents
    ranked = []
    for s in scopes:
        for k, entry in v.get(s, {}).items():
            match = 2 if k in keys else (1 if any(q and q in k for q in keys) else 0)
            if keys and not match:
                continue
            for conf, line in _lines(s, k, entry):
                tag_hit = any(t in line.lower() for t in tags)
                ranked.append(((match, tag_hit, conf, entry["ts"]), line))
    ranked.sort(key=lambda r: r[0], reverse=True)
    out, used = [], 0
    for _, line in ranked:
        if used + len(line) > budget_chars:
            break
        out.append(line)
        used += len(line) + 1
    RECALL_STATS["calls"] += 1
    RECALL_STATS["chars"] += used
    _emit(agent, "recall", out)
    return out


def get(scope: str, key: str) -> dict:
    """Raw entry for numeric logic (repeat-seller anchor etc). Empty when brain is OFF."""
    if not ENABLED:
        return {}
    return view()["scopes"].get(scope, {}).get(key, {})


# ---------- ops ----------

def stats() -> dict:
    evs = events()
    v = view(evs)
    per_scope = {s: sum(1 for e in evs if e["scope"] == s) for s in SCOPES}
    return {"enabled": ENABLED, "events": len(evs), "bytes": LOG.stat().st_size if LOG.exists() else 0,
            "per_scope": per_scope, "keys": {s: len(v["scopes"][s]) for s in SCOPES},
            "conflicts": len(v["conflicts"])}


def playbook() -> list[dict]:
    """Tactic x segment win-rate table for the Brain tab and tactic picking."""
    rows = []
    for k, entry in view()["scopes"]["playbook"].items():
        for c in entry["counters"].values():
            if isinstance(c, dict) and "tries" in c:
                tactic, _, segment = k.partition("|")
                rows.append({"tactic": tactic, "segment": segment, "tries": c["tries"],
                             "wins": c.get("wins", 0), "saved": c.get("saved", 0), "rate": c.get("wins", 0) / c["tries"] if c["tries"] else 0})
    return sorted(rows, key=lambda r: (r["segment"], -r["rate"]))


def reset() -> None:
    global _events, _loaded
    with _lock:
        if LOG.exists():
            LOG.unlink()
        _events, _loaded = [], True


def snapshot(name: str) -> Path:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    dst = SNAPSHOTS / f"{name}.jsonl"
    with _lock:
        if LOG.exists():
            shutil.copyfile(LOG, dst)
        else:
            dst.write_text("", encoding="utf-8")
    return dst


def load(name: str) -> int:
    global _loaded
    src = SNAPSHOTS / f"{name}.jsonl"
    if not src.exists():
        raise FileNotFoundError(f"no snapshot {name!r}")
    with _lock:
        DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, LOG)
        _loaded = False
    return len(events())
