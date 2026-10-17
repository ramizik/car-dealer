"""Live seller: the agent calls, a person answers in the browser, the negotiator reads the answer.

Plugs into agents.negotiate where the sim seller would go: `await seller.respond(offer, tactic)`.
That call waits here until the browser posts the seller's answer (audio or typed). No answer in TIMEOUT_S seconds
and the sim seller answers that round, so the demo never hangs.
One deal per shift uses this (swarm.py); the other deals are simulated so the demo keeps moving without a person.
"""
import asyncio
import re
import time

import llm

TIMEOUT_S = 60
PENDING: dict[str, asyncio.Future] = {}  # deal id -> the answer the negotiator is waiting for

PARSE_SYSTEM = (
    "A used-car seller answered our offer on a phone call. Read what they said. Return JSON "
    '{"accepted": bool, "walked_away": bool, "counter": int or null}. '
    "accepted = they agree to our offer. walked_away = they refuse or end the talk. "
    "counter = the price they asked for, in dollars, if they named one. Dollars only, no text."
)
_YES = re.compile(r"\b(yes|yeah|deal|sold|agreed?|works|sure|okay|ok)\b", re.I)
_NO = re.compile(r"\b(no|nope|not interested|forget it|goodbye|bye|walk)\b", re.I)
_NUM = re.compile(r"\$?\s?(\d{1,3}(?:,\d{3})+|\d{4,6})\b")


def answer(deal_id: str, text: str) -> dict:
    """Browser posts the seller's answer (already transcribed). Resolves the waiting round."""
    fut = PENDING.get(deal_id)
    if fut is None or fut.done():
        return {"ok": False, "error": "not waiting for a seller answer"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "nothing heard, try again or type it"}
    fut.set_result(text)
    return {"ok": True, "text": text}


def _rules(text: str, offer: int) -> tuple[bool, bool, int | None]:
    """Offline reading of a seller answer, used when the model is not live."""
    nums = [int(n.replace(",", "")) for n in _NUM.findall(text)]
    counter = max(nums) if nums else None
    if counter is not None and counter <= offer:
        return True, False, None  # named a price at or under our offer: that is a yes
    if _NO.search(text) and not counter:
        return False, True, None
    if _YES.search(text) and not _NO.search(text):
        return True, False, None
    return False, False, counter


async def read_answer(text: str, offer: int) -> tuple[bool, int | None]:
    """(accepted, counter). counter None with accepted False means the seller walked away."""
    v = await llm.chat_json(PARSE_SYSTEM, f"Our offer: ${offer:,}\nSeller said: {text}", tier="fast")
    if not isinstance(v, dict) or not v:
        accepted, walked, counter = _rules(text, offer)
    else:
        accepted, walked = bool(v.get("accepted")), bool(v.get("walked_away"))
        counter = v.get("counter")
        counter = int(counter) if isinstance(counter, (int, float)) and counter > 0 else None
    # A price above our offer is a counter, not a walk-away, even if the model said otherwise.
    if counter is not None and counter > offer:
        accepted, walked = False, False
    if accepted:
        return True, None
    if walked:
        return False, None
    return False, counter


class LiveSeller:
    """Same interface as sim.Seller: opening(), respond(offer, tactic), public()."""

    def __init__(self, deal: dict, fallback, emit):
        self.deal, self.fallback, self.emit = deal, fallback, emit
        self.patience_left = 5
        self.abandoned = False  # nobody picked up once: the sim seller carries the rest of the call

    def opening(self) -> str:
        return ""  # the seller has not spoken yet; the first real words come from the browser

    def public(self) -> dict:
        return {"patience_left": self.patience_left}

    async def respond(self, offer: int, tactic: str | None = None) -> tuple[bool, int | None, str]:
        deal_id = self.deal["id"]
        if self.abandoned:
            return await self.fallback.respond(offer, tactic)
        self.deal["turn"] = {"who": "seller", "action": "answer", "since": time.time(), "offer": offer}
        fut = asyncio.get_running_loop().create_future()
        PENDING[deal_id] = fut
        try:
            text = await asyncio.wait_for(fut, TIMEOUT_S)
        except asyncio.TimeoutError:
            self.abandoned = True
            self.emit("negotiator", "state", "No answer from the seller, the sim seller answers this round",
                      {"deal_id": deal_id, "timeout": True})
            return await self.fallback.respond(offer, tactic)
        finally:
            PENDING.pop(deal_id, None)
            self.deal["turn"] = {"who": "system", "action": "reply", "since": time.time()}
        self.patience_left -= 1
        accepted, counter = await read_answer(text, offer)
        return accepted, counter, text
