"""Swarm agents. Rule: every agent starts with brain.recall(...) and ends with brain.write(...).

Prices are decided in code (deterministic, clamped to max_buy); the LLM only writes the words.
"""
import asyncio
import inspect
import os
import random
import re

import brain
import conversations
import dealer_memory
import dealer_profile
import vector_memory
import llm
from agent_tiers import tier_for
import outreach
import seller_agent
import skills
import voice

# Tactic names are shared with sim.py (names only; the persona -> weak_to mapping stays hidden there).
TACTICS = ["fast_cash_pickup", "comps_anchor", "split_difference", "volume_relationship", "walk_away_threat"]
DEFAULT_TACTIC = "comps_anchor"  # brain OFF: classic lowball citing comps
SEGMENTS = ["motivated_private", "price_anchored", "haggler", "wholesaler_repeat", "unknown"]
MAX_ROUNDS = 6
OPEN_PCT = 0.78  # same opening for every tactic, so measured gains come from the tactic, not the anchor
STEP = 0.35  # fraction of the gap closed each round
PRIOR_SAVED = 0.3  # optimistic: above any realistic saving, forces exploration of untried tactics
DISCLOSURE = "(Heads up: I'm an AI assistant buying on behalf of {dealer}.)"
USE_LLM_TEXT = os.getenv("AGENT_TEXT", "1") == "1"  # eval sets 0 to save calls

KEYWORDS = {
    "motivated_private": ["moving", "need it gone", "asap", "quick sale", "relocat", "baby", "divorce", "deploy",
                          "gone", "fast", "this weekend", "done fast", "has to go", "move next"],
    "price_anchored": ["kbb", "blue book", "firm", "worth", "edmunds", "not budging", "know what it's worth",
                       "comps", "fair", "higher than", "looked up"],
    "haggler": ["best offer", "make me an offer", "negotiable", "obo", "talk me", "let's deal",
                "middle", "come up", "make a deal", "not that low"],
    "wholesaler_repeat": ["lot", "inventory", "dealer", "wholesale", "another one", "units", "auction",
                          "more coming", "regularly", "repeat buyer", "move a lot", "send inventory"],
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
        seller_text, tier=tier_for("buyer/marketplace"))
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


# Offline wording. Several lines per tactic so follow-up rounds never repeat word for word.
FOLLOW_UPS = {
    "fast_cash_pickup": ["I can pay ${o} cash and pick it up this week, no hassle.",
                         "Cash in hand, ${o}, and we handle the pickup on your schedule.",
                         "${o}, paid on the spot. You won't have to deal with strangers or test drives.",
                         "Final push from me: ${o} cash, picked up whenever suits you."],
    "comps_anchor": ["Similar ones nearby are going for less; ${o} is fair{m}.",
                     "I checked recent sales of this model. ${o} lines up with what they sell for{m}.",
                     "Going by comparable listings, ${o} is a strong number for this one.",
                     "The market supports ${o}. That's me stretching to the top of the comps."],
    "split_difference": ["Let's meet in the middle: ${o}.",
                         "We're close. Splitting it puts us at ${o}.",
                         "I'll move again if you do. ${o} gets us both there.",
                         "Halfway is ${o}. Can we shake on that?"],
    "volume_relationship": ["${o} works for us, and we buy regularly, so there's more business after this one.",
                            "We buy a lot of these. At ${o} you'd have a repeat buyer, not a one-off.",
                            "${o} today, and we'll call you first next time you have one to sell.",
                            "I can go to ${o}. We'd like this to be the first of many deals."],
    "walk_away_threat": ["${o} is where I am, otherwise I'll look at the other one I found.",
                         "I have another option lined up. ${o} keeps me with yours.",
                         "${o} is as far as I can go before I move on.",
                         "Last offer from me: ${o}. After that I'll take the other truck."],
}
NODS = ["I hear you on ${c}. ", "Thanks for coming down to ${c}. ", "${c} is more than I can do. ", ""]


def _template(tactic, offer, round_, comps_mid=None, counter=None):
    m = f" against a ${comps_mid:,.0f} market" if comps_mid else ""
    lines = FOLLOW_UPS.get(tactic, ["I can offer ${o}."])
    if not round_:
        return "Hi! Interested in your car. " + lines[0].replace("${o}", f"${offer:,.0f}").replace("{m}", m)
    line = lines[round_ % len(lines)].replace("${o}", f"${offer:,.0f}").replace("{m}", m)  # lines[0] was the opening
    nod = NODS[round_ % len(NODS)].replace("${c}", f"${counter:,.0f}") if counter else ""
    return nod + line


async def _message(deal, tactic, offer, round_, seller_text, memory, party="", skill_text="", counter=None, previous=()):
    comps = deal.get("comps_mid")
    if not USE_LLM_TEXT or llm._client is None:
        return _template(tactic, offer, round_, comps, counter)
    car = deal.get("car") or deal.get("listing", {}).get("title", "the car")
    # Only the buyer-talk skill and the last few turns from the conversation file go to the model.
    history = conversations.recent(party) if party else ""
    text = await llm.chat(
        "You are a used-car buyer negotiating by text for a dealership. Write ONE short message (<=40 words). "
        f"Use the tactic '{tactic}'. State our offer of exactly ${offer:,.0f}. You may mention the seller's last number, "
        "but no other price. React to what they just said. Never reuse wording from your earlier messages. No emojis.\n\n"
        + skill_text,
        f"Car: {car}\nSeller said: {seller_text or '(listing only)'}\nMarket comps mid: {comps}\n"
        f"Recent conversation:\n{history or '(first message)'}\n"
        f"Their last number: {f'${counter:,.0f}' if counter else 'none yet'}\n"
        f"Your earlier messages (do not repeat their wording):\n" + ("\n".join(previous[-3:]) or "(none)") + "\n"
        f"Shared memory:\n" + ("\n".join(memory[:6]) or "(none)"),
        tier=tier_for("buyer/outreach"), temperature=0.4)
    text = text.strip()
    # LLM must not invent prices: fall back if the offer is missing or another $ amount appears
    amounts = {int(re.sub(r"[^\d]", "", a)) for a in re.findall(r"\$[\d,]+", text)}
    allowed = {int(offer)} | ({int(counter)} if counter else set())
    ok = text and int(offer) in amounts and amounts <= allowed and text not in previous
    return text if ok else _template(tactic, offer, round_, comps, counter)


def _ask_seller_agent(deal: dict, buy_price: float, emit, deal_id: str) -> dict:
    """Buyer -> seller agent: 'if we pay X, what can we sell it for, how fast, and what do we make?'"""
    emit("negotiator", "message", f"Asked sales desk: if we pay ${buy_price:,.0f}, what can we sell it for?",
         {"deal_id": deal_id, "kind": "ask_seller_agent", "buy_price": buy_price})
    q = seller_agent.quote(deal, buy_price)
    if q["resale_price"]:
        text = (f"Sell for about ${q['resale_price']:,.0f} in ~{q['days_to_sell']:.0f} days ({q['days_source']}); "
                f"profit ~{seller_agent.usd(q['profit'])}. {'Go ahead.' if q['verdict'] == 'buy' else 'Pass: ' + '; '.join(q['reasons'])}")
    else:
        text = "Can't price a resale yet (no market value). Go ahead, but check comps."
    emit("seller_agent", "message", text, {"deal_id": deal_id, "kind": "resale_quote", **q})
    return q


# Demo pacing: a random pause between negotiation messages, so the run looks like people talking, not a script.
# 0 and 0 for eval and tests.
PACE_MIN = float(os.getenv("DEMO_PACE_MIN", "0"))
PACE_MAX = float(os.getenv("DEMO_PACE_MAX", "0"))


def pace() -> float:
    return random.uniform(PACE_MIN, max(PACE_MIN, PACE_MAX))


def bubble(t: dict) -> dict:
    """A transcript line as the dashboard chat shows it."""
    return {k: v for k, v in {"from": t["from"], "text": t["text"], "tactic": t.get("tactic"), "channel": t.get("channel"),
                              "recalled": t.get("recalled") or None, "audio_url": t.get("audio_url")}.items() if v}


def show(deal: dict, t: dict) -> None:
    """Live deals: each line reaches the deal's chat as it is said, so the browser sees the call in progress."""
    if deal.get("chat_sink") is not None and t.get("text") and t["from"] in ("agent", "seller"):
        deal["chat_sink"].append(bubble(t))


async def negotiate(deal: dict, seller, epsilon: float = 0.0, emit=_noop_emit, rng=None) -> dict:
    """Buy-side negotiation, <= MAX_ROUNDS. `seller.respond(offer, tactic) -> (accepted, counter, text)`.

    deal: {id, ask, max_buy, seller_id, car?, comps_mid?, seller_text?, dealer?}
    """
    rng = rng or random.Random(hash(deal.get("id", "")))
    deal_id, party = deal.get("id", "D-?"), f"seller:{deal.get('seller_id', 'unknown')}"
    ask, max_buy = float(deal["ask"]), float(deal["max_buy"])
    seller_text = deal.get("seller_text") or (seller.opening() if hasattr(seller, "opening") else "")
    dealer = deal.get("dealer", "Joe's Auto")
    voice_on = bool(deal.get("voice"))  # voice mode: speak agent lines, transcribe seller audio when given
    if voice_on and deal.get("seller_audio"):
        seller_text = voice.transcribe(deal["seller_audio"]) or seller_text

    # recall: what we know about this seller and the dealer
    memory = brain.recall(["party", "dealer"], keys=[party, deal.get("dealer_key", "joes-auto")], agent="negotiator")
    skill = skills.load("buyer/outreach", voice=voice_on)  # read-before: own skill + top mistakes
    memory = skill["mistakes"] + memory
    emit("negotiator", "skill", f"read {', '.join(skill['files'])}", {"deal_id": deal_id, "mistakes": skill["mistakes"]})
    emit("negotiator", "recall", f"{len(memory)} memories", {"deal_id": deal_id, "lines": memory})
    segment = await classify_segment(seller_text)
    known = brain.get("party", party)
    if (known.get("facts", {}).get("segment") or {}).get("value") in SEGMENTS and segment == "unknown":
        segment = known["facts"]["segment"]["value"]
    tactic = pick_tactic(segment, epsilon, rng)
    pb = brain.recall("playbook", keys=[f"|{segment}"], agent="negotiator", budget_chars=400)
    memory += pb
    # Tier 3: similar past deals from the long-term vector store (filtered to what the buyer may see).
    similar = vector_memory.search(f"{deal.get('car', '')} {seller_text}", agent="negotiator", scopes=["deals", "lessons", "mistakes"])
    if similar:
        memory += [f"similar past: {s['text']}" for s in similar]
        emit("negotiator", "recall", f"{len(similar)} similar past deals", {"deal_id": deal_id, "lines": [s["text"] for s in similar]})
    emit("negotiator", "recall", f"segment={segment}, tactic={tactic}", {"deal_id": deal_id, "lines": pb})

    # repeat seller: their last settled share of ask sets a better opening, not a hard ceiling
    # (a hard cap from a different car pushed offers under the new car's floor and lost the deal)
    cap = max_buy
    open_pct = OPEN_PCT
    last = (known.get("facts", {}).get("last_counter_pct") or {}).get("value")
    if isinstance(last, (int, float)):
        open_pct = max(OPEN_PCT, float(last) - 0.04)

    # The dealer's setup: only buy if they asked us to, and never above their per-car limit.
    profile = dealer_profile.get()
    if "buy" not in profile["services"]:
        dropped = "dealer setup: buying is turned off"
        emit("negotiator", "state", f"Dropped {deal_id}: {dropped}", {"deal_id": deal_id, "closed": False, "price": None})
        return {"deal_id": deal_id, "closed": False, "price": None, "rounds": 0, "tactic": tactic, "segment": segment,
                "ask": ask, "max_buy": max_buy, "dropped": dropped, "transcript": [], "recalled": memory}
    max_buy = min(max_buy, profile["buy_limit"])
    cap = min(cap, max_buy)

    # Learned from the dealer: stop bidding on models they keep declining.
    skip, why = dealer_memory.should_skip(deal.get("car") or deal.get("listing", {}).get("title", ""))
    if skip:
        dropped = f"dealer preference: {why}"
        emit("negotiator", "state", f"Dropped {deal_id}: {dropped}", {"deal_id": deal_id, "closed": False, "price": None})
        return {"deal_id": deal_id, "closed": False, "price": None, "rounds": 0, "tactic": tactic, "segment": segment,
                "ask": ask, "max_buy": max_buy, "dropped": dropped, "transcript": [], "recalled": memory}

    # Coordinate with the seller agent before spending: resale price, days to sell, profit at our max.
    q = _ask_seller_agent(deal, max_buy, emit, deal_id)
    profit_cap = (q["resale_price"] - seller_agent.RECON - seller_agent.min_profit()) if q["resale_price"] else None
    too_slow = bool(q["days_to_sell"] and q["days_to_sell"] > seller_agent.MAX_DAYS)
    no_margin = profit_cap is not None and profit_cap < ask * OPEN_PCT * 0.8  # can't profit at any realistic offer
    if too_slow or no_margin:
        dropped = f"sales desk: {q['reasons'][0]}"
        emit("negotiator", "state", f"Dropped {deal_id}: {dropped}", {"deal_id": deal_id, "closed": False, "price": None})
        return {"deal_id": deal_id, "closed": False, "price": None, "rounds": 0, "tactic": tactic, "segment": segment,
                "ask": ask, "max_buy": max_buy, "dropped": dropped, "transcript": [], "recalled": memory, "resale_quote": q}
    if profit_cap is not None:
        # Never pay more than leaves the minimum profit after resale and recon.
        max_buy = min(max_buy, profit_cap)
        cap = min(cap, max_buy)

    offer = round(min(cap, ask * open_pct), -1)
    channel = outreach.channel_for(segment, "seller", deal.get("channels"))
    transcript, counter, closed, price, dropped = [], None, False, None, ""
    for r in range(MAX_ROUNDS):
        previous = [t["text"] for t in transcript if t["from"] == "agent"]
        msg = await _message(deal, tactic, offer, r, seller_text, memory, party, skill["text"], counter, previous)
        if r == 0:
            msg = f"{msg} {DISCLOSURE.format(dealer=dealer)}"
        msg = outreach.shape(channel, msg, first=(r == 0))
        conversations.append(party, "agent", msg, tag=f"${offer:,.0f}, {tactic}, {channel}")
        entry = {"from": "agent", "text": msg, "channel": channel, "offer": offer, "tactic": tactic, "recalled": memory[:6] if r == 0 else []}
        if voice_on and (audio := voice.speak(msg)):
            entry["audio_url"] = voice.clip_url(voice.to_wav(audio, 44100))
        transcript.append(entry)
        show(deal, entry)
        emit("negotiator", "message", msg, {"deal_id": deal_id, "offer": offer, "tactic": tactic, "channel": channel})
        if PACE_MAX and not voice_on:
            await asyncio.sleep(pace())

        reply = seller.respond(int(offer), tactic)
        accepted, counter, seller_text = await reply if inspect.isawaitable(reply) else reply
        if seller_text:
            conversations.append(party, "seller", seller_text)
        transcript.append({"from": "seller", "text": seller_text, "counter": counter})
        show(deal, transcript[-1])
        emit("seller", "message", seller_text, {"deal_id": deal_id, "counter": counter})
        if PACE_MAX and not voice_on:
            await asyncio.sleep(pace())

        if re.search(r"https?://", seller_text or ""):
            dropped = "seller sent an off-platform payment link"
            brain.write("negotiator", "party", party, "fact", True, attr="red_flag", confidence=0.9, source=f"chat:{deal_id}")
            emit("negotiator", "blocked", f"Red flag: {dropped}", {"deal_id": deal_id})
            skills.record_mistake("buyer/outreach", "Off-platform payment link in seller chat: flag the party, never open it")
            break

        # Interested seller: ask once for a callback number, or take the number they just gave.
        phone = voice.extract_phone(seller_text or "")
        if phone:
            masked = voice.record_callback(party, phone)
            brain.write("negotiator", "party", party, "fact", masked, attr="callback_masked", confidence=0.9, source=f"chat:{deal_id}")
            ack = f"Thanks, the desk will ring you on {masked} to set up the call."
            transcript.append({"from": "agent", "text": ack, "kind": "callback_set", "recalled": []})
            emit("negotiator", "callback", ack, {"deal_id": deal_id, "phone": masked})
        if r == 0 and segment == "unknown":
            segment = await classify_segment(seller_text)
            if segment != "unknown":  # re-pick so the playbook credits the tactic actually used for this segment
                tactic = pick_tactic(segment, epsilon, rng)
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
        left = seller.public().get("patience_left", MAX_ROUNDS - r - 1) if hasattr(seller, "public") else MAX_ROUNDS - r - 1
        last_chance = left <= 1 or r == MAX_ROUNDS - 2
        offer = round(target if last_chance else offer + (target - offer) * STEP, -1)
        offer = min(offer, max_buy)  # hard clamp in code, never trust the model
    else:
        dropped = "no deal within round limit"
    if closed and not voice.CALLBACKS.get(party):
        # Interested now: ask once for a number so the desk can arrange pickup by phone.
        question = "Great, we have a deal. What number should the desk ring you on to arrange pickup?"
        transcript.append({"from": "agent", "text": question, "kind": "ask_number", "recalled": []})
        show(deal, transcript[-1])
        emit("negotiator", "message", question, {"deal_id": deal_id, "kind": "ask_number"})

    # write: what we learned, for every future agent
    brain.write("negotiator", "playbook", f"{tactic}|{segment}", "counter", {"tries": 1, "wins": int(closed), "saved": round((ask - price) / ask, 4) if closed else 0}, source=f"chat:{deal_id}")
    brain.write("negotiator", "party", party, "fact", segment, attr="segment", confidence=0.7, source=f"chat:{deal_id}")
    if counter is not None:
        final = price if closed else counter  # what they actually settled at, or their last number
        brain.write("negotiator", "party", party, "fact", round(final / ask, 4), attr="last_counter_pct", confidence=0.8, source=f"chat:{deal_id}")
    hint = transcript[1]["text"][:120] if len(transcript) > 1 else ""
    brain.write("negotiator", "party", party, "note",
                f"{segment}: {tactic} {'closed at $%s' % f'{price:,.0f}' if closed else 'failed (' + dropped + ')'}; said: {hint}",
                confidence=0.7, source=f"chat:{deal_id}")

    if closed:
        # Confirm with the seller agent at the real price, and keep the answer in team memory.
        q = _ask_seller_agent(deal, price, emit, deal_id)
        if q["resale_price"]:
            brain.write("seller_agent", "market", f"resale|{seller_agent.model_key(deal)}", "note",
                        f"bought ${price:,.0f}; resale ~${q['resale_price']:,.0f}, ~{q['days_to_sell']:.0f} days "
                        f"({q['days_source']}), profit ~{seller_agent.usd(q['profit'])}", confidence=0.6, source=f"quote:{deal_id}")

    sell_pitches = []
    if closed:  # selling agent starts reaching buyers right away, each on their own channel
        resale = (q or {}).get("resale_price") or price
        buyers = deal.get("buyers") or [{"id": f"{deal_id}-{p[:3]}", "persona": p} for p in ("motivated_private", "wholesaler_repeat", "haggler")]
        sell_pitches = outreach.sell_outreach({**deal, "id": deal_id}, buyers, resale, emit, deal.get("channels"))

    result = {"deal_id": deal_id, "closed": closed, "price": price, "rounds": sum(t["from"] == "agent" for t in transcript),
              "tactic": tactic, "segment": segment, "channel": channel, "ask": ask, "max_buy": max_buy, "dropped": dropped,
              "transcript": transcript, "recalled": memory, "resale_quote": q, "sell_outreach": sell_pitches}
    emit("negotiator", "state", f"{'Agreed' if closed else 'Dropped'} {deal_id}" + (f" at ${price:,.0f}" if closed else f": {dropped}"),
         {"deal_id": deal_id, "closed": closed, "price": price})
    return result
