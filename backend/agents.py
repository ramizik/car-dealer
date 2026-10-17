"""Swarm agents. Rule: every agent starts with brain.recall(...) and ends with brain.write(...).

Prices are decided in code (deterministic, clamped to max_buy); the LLM only writes the words.
"""
import base64
import os
import random
import re

import brain
import llm
import voice

# Canonical tactic names. sim.py personas pick their hidden `weak_to` from this list.
TACTICS = ["anchor_low", "fast_cash_pickup", "cite_comps", "meet_halfway", "walk_away_threat"]
DEFAULT_TACTIC = "anchor_low"
SEGMENTS = ["motivated_private", "price_anchored", "haggler", "wholesaler_repeat", "unknown"]
MAX_ROUNDS = 6
OPEN_PCT = 0.78  # same opening for every tactic, so measured gains come from the tactic, not the anchor
STEP = 0.35  # fraction of the gap closed each round
PRIOR_SAVED = 0.3  # optimistic: above any realistic saving, forces exploration of untried tactics
DISCLOSURE = "(Heads up: I'm an AI assistant buying on behalf of {dealer}.)"
USE_LLM_TEXT = os.getenv("AGENT_TEXT", "1") == "1"  # eval sets 0 to save calls

KEYWORDS = {
    "motivated_private": ["moving", "need it gone", "asap", "quick sale", "relocat", "baby", "divorce", "deploy"],
    "price_anchored": ["kbb", "blue book", "firm", "worth", "edmunds", "not budging", "know what it's worth"],
    "haggler": ["best offer", "make me an offer", "negotiable", "obo", "talk me", "let's deal"],
    "wholesaler_repeat": ["lot", "inventory", "dealer", "wholesale", "another one", "units", "auction"],
}


def _noop_emit(agent, type_, text, data=None):
    pass


# ---------- 2.B4 segment classifier ----------

def _keyword_segment(text: str) -> str:
    t = text.lower()
    scores = {seg: sum(w in t for w in words) for seg, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "unknown"


async def classify_segment(seller_text: str) -> str:
    """Nano classifies the seller; keyword fallback if the call fails or returns junk."""
    kw = _keyword_segment(seller_text)
    if llm._client is None or not seller_text.strip():
        return kw
    out = await llm.chat_json(
        "Classify a used-car seller from their message. Segments: motivated_private (needs fast sale), "
        "price_anchored (fixated on book value), haggler (enjoys bargaining), wholesaler_repeat (dealer/lot "
        'moving inventory), unknown. Return {"segment": "<one>"}.',
        seller_text, tier="fast")
    seg = out.get("segment") if isinstance(out, dict) else None
    return seg if seg in SEGMENTS and seg != "unknown" else kw


# ---------- 2.B5 negotiator ----------

def pick_tactic(segment: str, epsilon: float = 0.0, rng=random) -> str:
    """Brain ON: best smoothed win rate for this segment (+epsilon exploration). Brain OFF: default."""
    if not brain.ENABLED:
        return DEFAULT_TACTIC
    if rng.random() < epsilon:
        return rng.choice(TACTICS)
    rows = {r["tactic"]: r for r in brain.playbook() if r["segment"] == segment}
    def score(t):  # mean fraction of ask saved per try; optimistic prior so untried tactics get tried
        r = rows.get(t, {"tries": 0, "saved": 0})
        return (r["saved"] + PRIOR_SAVED) / (r["tries"] + 1)
    return max(TACTICS, key=lambda t: (score(t), t == DEFAULT_TACTIC))


def _template(tactic, offer, round_, comps_mid=None):
    lines = {
        "anchor_low": f"I can do ${offer:,.0f} today.",
        "fast_cash_pickup": f"I can pay ${offer:,.0f} cash and pick it up this week, no hassle.",
        "cite_comps": f"Similar ones nearby are going for less; ${offer:,.0f} is fair" + (f" against a ${comps_mid:,.0f} market." if comps_mid else "."),
        "meet_halfway": f"Let's meet in the middle: ${offer:,.0f}.",
        "walk_away_threat": f"${offer:,.0f} is where I am, otherwise I'll look at the other one I found.",
    }
    return lines.get(tactic, f"I can offer ${offer:,.0f}.") if round_ else f"Hi! Interested in your car. {lines.get(tactic)}"


async def _message(deal, tactic, offer, round_, seller_text, memory):
    comps = deal.get("comps_mid")
    if not USE_LLM_TEXT or llm._client is None:
        return _template(tactic, offer, round_, comps)
    car = deal.get("car") or deal.get("listing", {}).get("title", "the car")
    text = await llm.chat(
        "You are a used-car buyer negotiating by text for a dealership. Write ONE short message (<=40 words). "
        f"Use the tactic '{tactic}'. State exactly ${offer:,.0f} and no other price. No emojis.",
        f"Car: {car}\nSeller said: {seller_text or '(listing only)'}\nMarket comps mid: {comps}\n"
        f"Shared memory:\n" + ("\n".join(memory) or "(none)"),
        tier="smart", temperature=0.4)
    text = text.strip()
    # LLM must not invent prices: fall back if the offer is missing or another $ amount appears
    amounts = {int(re.sub(r"[^\d]", "", a)) for a in re.findall(r"\$[\d,]+", text)}
    return text if text and amounts == {int(offer)} else _template(tactic, offer, round_, comps)


async def negotiate(deal: dict, seller, epsilon: float = 0.0, emit=_noop_emit, rng=None) -> dict:
    """Buy-side negotiation, <= MAX_ROUNDS. `seller.respond(offer, tactic) -> (accepted, counter, text)`.

    deal: {id, ask, max_buy, seller_id, car?, comps_mid?, seller_text?, dealer?}
    """
    rng = rng or random.Random(hash(deal.get("id", "")))
    deal_id, party = deal.get("id", "D-?"), f"seller:{deal.get('seller_id', 'unknown')}"
    ask, max_buy = float(deal["ask"]), float(deal["max_buy"])
    seller_text = deal.get("seller_text", "")
    dealer = deal.get("dealer", "Joe's Auto")
    voice_on = bool(deal.get("voice"))  # voice mode: speak agent lines, transcribe seller audio when given
    if voice_on and deal.get("seller_audio"):
        seller_text = voice.transcribe(deal["seller_audio"]) or seller_text
    asked_number = False

    # recall: what we know about this seller and the dealer
    memory = brain.recall(["party", "dealer"], keys=[party, deal.get("dealer_key", "joes-auto")], agent="negotiator")
    emit("negotiator", "recall", f"{len(memory)} memories", {"deal_id": deal_id, "lines": memory})
    segment = await classify_segment(seller_text)
    known = brain.get("party", party)
    if (known.get("facts", {}).get("segment") or {}).get("value") in SEGMENTS and segment == "unknown":
        segment = known["facts"]["segment"]["value"]
    tactic = pick_tactic(segment, epsilon, rng)
    pb = brain.recall("playbook", keys=[f"|{segment}"], agent="negotiator", budget_chars=400)
    memory += pb
    emit("negotiator", "recall", f"segment={segment}, tactic={tactic}", {"deal_id": deal_id, "lines": pb})

    # repeat seller: their last counter is a better ceiling than max_buy
    cap = max_buy
    last = (known.get("facts", {}).get("last_counter") or {}).get("value")
    if isinstance(last, (int, float)):
        cap = min(cap, float(last))

    offer = round(min(cap, ask * OPEN_PCT), -1)
    transcript, counter, closed, price, dropped = [], None, False, None, ""
    for r in range(MAX_ROUNDS):
        msg = await _message(deal, tactic, offer, r, seller_text, memory)
        if r == 0:
            msg = f"{msg} {DISCLOSURE.format(dealer=dealer)}"
        entry = {"from": "agent", "text": msg, "offer": offer, "tactic": tactic, "recalled": memory[:6] if r == 0 else []}
        if voice_on and (audio := voice.speak(msg)):
            entry["audio_b64"] = base64.b64encode(audio).decode()
        transcript.append(entry)
        emit("negotiator", "message", msg, {"deal_id": deal_id, "offer": offer, "tactic": tactic})

        accepted, counter, seller_text = seller.respond(offer, tactic)
        transcript.append({"from": "seller", "text": seller_text, "counter": counter})
        emit("seller", "message", seller_text, {"deal_id": deal_id, "counter": counter})

        if re.search(r"https?://", seller_text or ""):
            dropped = "seller sent an off-platform payment link"
            brain.write("negotiator", "party", party, "fact", True, attr="red_flag", confidence=0.9, source=f"chat:{deal_id}")
            emit("negotiator", "blocked", f"Red flag: {dropped}", {"deal_id": deal_id})
            break

        # Interested seller: ask once for a callback number, or take the number they just gave.
        phone = voice.extract_phone(seller_text or "")
        if phone:
            masked = voice.record_callback(party, phone)
            brain.write("negotiator", "party", party, "fact", masked, attr="callback_masked", confidence=0.9, source=f"chat:{deal_id}")
            ack = f"Thanks, the desk will ring you on {masked} to set up the call."
            transcript.append({"from": "agent", "text": ack, "kind": "callback_set", "recalled": []})
            emit("negotiator", "callback", ack, {"deal_id": deal_id, "phone": masked})
        elif counter is not None and not asked_number and not accepted:
            asked_number = True
            ask = "Happy to set up a call. What number should the desk ring you on?"
            transcript.append({"from": "agent", "text": ask, "kind": "ask_number", "recalled": []})
            emit("negotiator", "message", ask, {"deal_id": deal_id, "kind": "ask_number"})
        if r == 0 and segment == "unknown":
            segment = await classify_segment(seller_text)
        if accepted:
            closed, price = True, offer
            break
        if counter is None:
            dropped = "seller walked away"
            break
        if counter <= max(offer * 1.02, offer + 200) and counter <= max_buy:
            closed, price = True, float(counter)  # close enough: take their number
            transcript.append({"from": "agent", "text": f"Deal at ${counter:,.0f}.", "offer": counter, "tactic": tactic, "recalled": []})
            break
        target = min(counter, cap)
        offer = round(target if r == MAX_ROUNDS - 2 else offer + (target - offer) * STEP, -1)
        offer = min(offer, max_buy)  # hard clamp in code, never trust the model
    else:
        dropped = "no deal within round limit"

    # write: what we learned, for every future agent
    brain.write("negotiator", "playbook", f"{tactic}|{segment}", "counter", {"tries": 1, "wins": int(closed), "saved": round((ask - price) / ask, 4) if closed else 0}, source=f"chat:{deal_id}")
    brain.write("negotiator", "party", party, "fact", segment, attr="segment", confidence=0.7, source=f"chat:{deal_id}")
    if counter is not None:
        brain.write("negotiator", "party", party, "fact", float(counter), attr="last_counter", confidence=0.8, source=f"chat:{deal_id}")
    hint = transcript[1]["text"][:120] if len(transcript) > 1 else ""
    brain.write("negotiator", "party", party, "note",
                f"{segment}: {tactic} {'closed at $%s' % f'{price:,.0f}' if closed else 'failed (' + dropped + ')'}; said: {hint}",
                confidence=0.7, source=f"chat:{deal_id}")

    result = {"deal_id": deal_id, "closed": closed, "price": price, "rounds": sum(t["from"] == "agent" for t in transcript),
              "tactic": tactic, "segment": segment, "ask": ask, "max_buy": max_buy, "dropped": dropped,
              "transcript": transcript, "recalled": memory}
    emit("negotiator", "state", f"{'Bought' if closed else 'Dropped'} {deal_id}" + (f" at ${price:,.0f}" if closed else f": {dropped}"),
         {"deal_id": deal_id, "closed": closed, "price": price})
    return result
