"""Librarian: the background consolidation step (Tier 2 -> Tier 3) and the brain's cleaner.

run() does three things, all deterministic so the measured gain stays honest:
1. Lessons: for each seller type, the best tactic with enough tries becomes one playbook note.
2. Mistakes: a failure reason seen in 2+ deal artifacts becomes a MISTAKES.md line for the buyer.
3. Compaction: duplicate counters are summed and repeated notes dropped. The rewrite is only kept if view()
   is byte-identical before and after, so the conflict-free merge rules are never changed.
"""
import json
import re
from collections import Counter, defaultdict

import brain
import skills

MIN_TRIES = 3  # a tactic needs this many tries before it is called a lesson
MIN_REPEATS = 2  # a failure reason needs this many deals before it is a mistake


def lessons() -> list[str]:
    best = {}
    for row in brain.playbook():
        if row["tries"] >= MIN_TRIES and (row["segment"] not in best or row["rate"] > best[row["segment"]]["rate"]):
            best[row["segment"]] = row
    out = []
    for seg, r in sorted(best.items()):
        line = f"lesson: {seg.replace('_', ' ')} sellers -> {r['tactic'].replace('_', ' ')} wins {r['wins']}/{r['tries']}"
        brain.write("librarian", "playbook", f"lesson|{seg}", "note", line, confidence=0.9, source="librarian")
        out.append(line)
    return out


def mistakes() -> list[str]:
    reasons = Counter()
    for entry in brain.view()["scopes"]["party"].values():
        for n in entry["notes"]:
            m = re.match(r"\[(FAILED|BLOCKED)\] no deal: (.+?);", n["text"])
            if m:
                reasons[m.group(2)] += 1
    out = []
    for reason, n in reasons.items():
        if n >= MIN_REPEATS:
            out.append(skills.record_mistake("buyer/outreach", f"Repeated miss: {reason}"))  # same line bumps hits
    return [o for o in out if o]


def _compacted(evs: list[dict]) -> list[dict]:
    counters, notes, keep = {}, {}, []
    for e in sorted(evs, key=brain._order):
        if e["kind"] == "counter" and not e.get("visible_to"):
            k = (e["scope"], e["key"], e.get("attr"))
            if k in counters:
                c = counters[k]
                c["value"] = brain._add_counter(c["value"], e["value"])
                c["ts"] = max(c["ts"], e["ts"])
            else:
                counters[k] = dict(e, value=json.loads(json.dumps(e["value"])))
        elif e["kind"] == "note" and not e.get("visible_to"):
            notes[(e["scope"], e["key"], brain._norm(e["value"]))] = e  # later same text wins, as in view()
        else:
            keep.append(e)
    return sorted(keep + list(counters.values()) + list(notes.values()), key=brain._order)


def compact() -> dict:
    """Shrink the log without changing what any agent recalls. Returns sizes before and after."""
    before = brain.stats()
    with brain._lock:
        brain._load_log()
        old = list(brain._events)
        new = _compacted(old)
        same = json.dumps(brain.view(old), sort_keys=True, default=str) == json.dumps(brain.view(new), sort_keys=True, default=str)
        if same and len(new) < len(old):
            tmp = brain.LOG.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(e) + "\n" for e in new), encoding="utf-8")
            tmp.replace(brain.LOG)
            brain._events[:] = new
    after = brain.stats()
    return {"events_before": before["events"], "events_after": after["events"],
            "kb_before": round(before["bytes"] / 1024, 1), "kb_after": round(after["bytes"] / 1024, 1), "applied": same}


def run(emit=None) -> dict:
    out = {"lessons": lessons(), "mistakes": mistakes(), "compaction": compact()}
    if emit:
        c = out["compaction"]
        emit("librarian", "write", f"Memory tidied: {c['events_before']} -> {c['events_after']} entries, "
             f"{len(out['lessons'])} lessons, {len(out['mistakes'])} new mistakes", out)
    return out
