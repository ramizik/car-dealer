"""Where and how the buying and selling agents reach each person. Simulated: nothing is sent anywhere.

Each person gets the channel that suits their segment, and the message is shaped for that channel.
Every outreach is logged in the party's conversation file and emitted as an "outreach" event.
"""
import conversations

# channel -> (label, max chars, greeting, sign-off)
CHANNELS = {
    "sms": ("Text message", 160, "Hi,", ""),
    "facebook": ("Facebook Marketplace", 240, "Hi! Is this still available?", ""),
    "craigslist": ("Craigslist email relay", 600, "Hello,", "Thanks, Joe's Auto"),
    "autotrader": ("Autotrader message", 400, "Hello,", "Joe's Auto"),
    "email": ("Email", 800, "Hello,", "Best regards, Joe's Auto"),
}

# segment -> channels in order of preference (first one the dealer has enabled wins)
SELLER_PREF = {  # people we buy from
    "motivated_private": ["sms", "facebook", "craigslist"],
    "price_anchored": ["craigslist", "autotrader", "email"],
    "haggler": ["facebook", "craigslist", "sms"],
    "wholesaler_repeat": ["email", "autotrader", "sms"],
}
BUYER_PREF = {  # people we sell to
    "motivated_private": ["sms", "facebook"],
    "price_anchored": ["autotrader", "email"],
    "haggler": ["facebook", "craigslist"],
    "wholesaler_repeat": ["email", "autotrader"],
}


def channel_for(segment: str, side: str, enabled: list[str] | None = None) -> str:
    """side: 'seller' (we buy from them) or 'buyer' (we sell to them). enabled=None means any channel."""
    prefs = (SELLER_PREF if side == "seller" else BUYER_PREF).get(segment, ["sms", "email"])
    return next((c for c in prefs if not enabled or c in enabled), prefs[0])


def shape(channel: str, text: str, first: bool = False) -> str:
    """Fit a message to the channel: greeting on the first line, sign-off on long channels, length cap."""
    _, cap, greet, sign = CHANNELS[channel]
    body = text.strip()
    if first and not body.lower().startswith(("hi", "hello")):
        body = f"{greet} {body}"
    if sign and first:
        body = f"{body}\n{sign}"
    return body if len(body) <= cap else body[: cap - 1].rstrip() + "…"


def reach_out(party: str, side: str, segment: str, text: str, emit, deal_id: str = "",
              enabled: list[str] | None = None, agent: str = "negotiator") -> dict:
    """First contact with one person on the right channel. Returns {channel, label, text}."""
    ch = channel_for(segment, side, enabled)
    msg = shape(ch, text, first=True)
    conversations.append(party, "agent", msg, tag=f"first contact via {ch}")
    emit(agent, "outreach", f"{CHANNELS[ch][0]} to {party}: {msg}",
         {"deal_id": deal_id, "party": party, "channel": ch, "label": CHANNELS[ch][0], "segment": segment})
    return {"channel": ch, "label": CHANNELS[ch][0], "text": msg}


def sell_outreach(car: dict, buyers: list[dict], asking: float, emit, enabled: list[str] | None = None) -> list[dict]:
    """Selling agent pitches a car to several buyers, each on their own channel.

    buyers: [{id, persona}]. Returns one record per buyer.
    """
    title = car.get("car") or " ".join(str(car.get(k, "")) for k in ("year", "make", "model")).strip() or "a car"
    pitch = {
        "motivated_private": f"{title} is ready to go this week at ${asking:,.0f}. Want to see it today?",
        "price_anchored": f"{title}, priced at ${asking:,.0f} against current comps. Full report available.",
        "haggler": f"{title} at ${asking:,.0f}. Open to a fair offer, come take a look.",
        "wholesaler_repeat": f"{title} available at ${asking:,.0f}. We turn inventory often, happy to be your regular source.",
    }
    out = []
    for b in buyers:
        seg = b.get("persona", "haggler")
        out.append({"buyer_id": b["id"], **reach_out(f"buyer:{b['id']}", "buyer", seg, pitch.get(seg, pitch["haggler"]),
                                                      emit, car.get("id", ""), enabled, agent="seller_agent")})
    return out
