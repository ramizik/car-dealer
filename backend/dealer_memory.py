"""What the dealer tells us, kept so the team acts on it next time.

record(car, yes, reason) saves each approve or decline, with the dealer's reason if given.
should_skip(car) says whether the dealer has declined this kind of car enough to stop bidding on it.

Counts go in the brain as counters (summed, order-independent). Reasons go in as notes.
"""
import re

import brain

SKIP_AFTER_DECLINES = 2  # decline this many more than approvals, and we stop buying this model


def model_key(car: str) -> str:
    """'2018 Toyota Tacoma SR5 · 61k mi' -> 'toyota tacoma'. Year and trim are ignored."""
    head = (car or "").split(" · ")[0]
    words = [w for w in head.split() if not re.fullmatch(r"\d{4}", w)]
    return " ".join(words[:2]).lower() or "unknown"


def record(car: str, yes: bool, reason: str = "") -> None:
    key = model_key(car)
    brain.write("dealer", "dealer", f"decisions|{key}", "counter", {"approved": 1} if yes else {"declined": 1},
                attr="decisions", confidence=1.0, source=f"decision:{key}")
    if reason.strip():
        verdict = "approved" if yes else "declined"
        brain.write("dealer", "dealer", f"decisions|{key}", "note", f"{key}: {verdict}, dealer said: {reason.strip()}",
                    confidence=1.0, source=f"decision:{key}")


def counts(car: str) -> dict:
    """Approvals and declines this dealer has given for this model."""
    c = brain.get("dealer", f"decisions|{model_key(car)}").get("counters", {}).get("decisions", {})
    return {"approved": int(c.get("approved", 0)), "declined": int(c.get("declined", 0))}


def should_skip(car: str) -> tuple[bool, str]:
    c = counts(car)
    if c["declined"] >= SKIP_AFTER_DECLINES and c["declined"] > c["approved"]:
        return True, f"you declined {c['declined']} of this model before"
    return False, ""
