"""The dealer's setup answers, saved in the brain and read by buying and selling.

save(answers) stores each answer as a dealer fact. get() returns the profile with the limits as numbers,
falling back to the recommended defaults for anything the dealer skipped.
"""
import brain

DEALER = "dealer-profile"
DEFAULTS = {
    "services": ["buy", "sell"],
    "decision_mode": "dealer_decides",
    "buy_limit": 30000,
    "min_profit": 1500,
}
NUMERIC = {"buy_limit", "min_profit"}


def save(answers: dict[str, list[str]]) -> dict:
    """answers: {question_id: [chosen values]} from the setup screen."""
    for qid, values in answers.items():
        if not values:
            continue
        value = values if len(values) > 1 else values[0]
        if qid in NUMERIC:
            value = float(values[0])
        brain.write("dealer", "dealer", DEALER, "fact", value, attr=qid, confidence=1.0, source="setup")
    return get()


def get() -> dict:
    facts = brain.get("dealer", DEALER).get("facts", {})
    profile = dict(DEFAULTS)
    for attr, f in facts.items():
        profile[attr] = f["value"]
    for k in NUMERIC:
        profile[k] = float(profile[k])
    if isinstance(profile["services"], str):
        profile["services"] = [profile["services"]]
    return profile


def needs_final_call() -> bool:
    """True when the dealer wants to approve every buy and sale themselves."""
    return get()["decision_mode"] != "within_limits"
