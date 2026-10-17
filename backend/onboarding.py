# Dealer onboarding questions. Source: backend/skills/dealer/onboarding/SKILL.md.
# Answers are not persisted yet; the app shows them and asks the dealer to confirm.

QUESTIONS = [
    {"id": "identity", "ask": "Legal name, dealer licence number, city and state, and who approves deals (name, phone or Telegram)."},
    {"id": "sell", "ask": "Which cars may we list for you, and on which platforms (storefront, Facebook Marketplace-style, Craigslist-style, Autotrader-style)? What fee per sale?"},
    {"id": "buy", "ask": "Which makes and models do you want, at what price band and mileage cap? Clean title only?"},
    {"id": "auction", "ask": "Which auctions may we bid at, and what is the max bid per car? Do you approve each bid first?"},
    {"id": "approvals", "ask": "What needs your YES: every buy, every sale below floor, every bid, every posting?"},
    {"id": "inventory", "ask": "Send your inventory: VIN, year, make, model, miles, asking price, floor, photos, title status, known issues."},
    {"id": "authority", "ask": "Do you authorise us to post your listings and bid on your behalf within these rules?"},
]
