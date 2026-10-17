"""Which Nemotron tier each agent uses. Tiers and model IDs live in llm.py (env-overridable).

Why this split: Crusoe limits are per model (30 RPM with no payment method), so spreading
agents across tiers spreads the load. Smart = reasoning and negotiation, fast = high-volume
extraction, sim = simulated counterparties and librarian.
"""

AGENT_TIERS: dict[str, str] = {
    # Owner and leads
    "owner": "smart",
    "buyer_lead": "smart",
    "seller_lead": "smart",
    # Buy swarm
    "buyer/kbb": "smart",             # numeric valuation, max_buy reasoning
    "buyer/marketplace": "fast",      # listing extraction, high volume
    "buyer/outreach": "smart",        # talks to sellers, negotiates
    # Sell swarm
    "seller/listing": "smart",        # writes the listing pack per channel
    "seller/enquiry": "smart",        # talks to buyers, closes
    "scout": "fast",                  # listing search subagent (= buyer/marketplace)
    "appraiser": "smart",             # market value from research (= buyer/kbb)
    # Dealer consignment and auction
    "dealer/onboarding": "fast",      # intake questions, saves answers
    "dealer/consignment-listing": "fast",
    "dealer/auction": "smart",        # bid decisions within max_bid
    # Simulated counterparties and librarian
    "sim/seller": "sim",
    "sim/buyer": "sim",
    "librarian": "sim",
}


def tier_for(agent: str) -> str:
    """Tier name for an agent. Unknown agents get the smart tier rather than failing a demo."""
    return AGENT_TIERS.get(agent, "smart")
