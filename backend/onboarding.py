# Dealer onboarding: multiple choice so a dealer can finish in about two minutes.
# Source of truth for the Dealer setup screen. Answers are not persisted yet.
# Every option has a value (stored) and a label (shown). "recommended" marks the default most dealers pick.

QUESTIONS = [
    {
        "id": "dealer_type",
        "ask": "What kind of dealership are you?",
        "type": "single",
        "options": [
            {"value": "independent", "label": "Independent used-car lot"},
            {"value": "franchise", "label": "Franchise dealer"},
            {"value": "wholesale", "label": "Wholesale only"},
        ],
    },
    {
        "id": "car_segments",
        "ask": "What kind of cars do you deal in?",
        "type": "multi",
        "options": [
            {"value": "premium", "label": "Premium (BMW, Mercedes, Audi, Lexus)"},
            {"value": "supercars", "label": "Supercars and sports cars"},
            {"value": "normal", "label": "Everyday cars (Civic, Corolla, Camry)", "recommended": True},
            {"value": "family", "label": "Family cars and SUVs (minivans, 3-row SUVs)"},
            {"value": "all", "label": "All of them"},
        ],
    },
    {
        "id": "sell_channels",
        "ask": "Where should we list your cars for sale?",
        "type": "multi",
        "options": [
            {"value": "storefront", "label": "Our website", "recommended": True},
            {"value": "facebook", "label": "Facebook Marketplace"},
            {"value": "craigslist", "label": "Craigslist"},
            {"value": "autotrader", "label": "Autotrader"},
        ],
    },
    {
        "id": "buy_types",
        "ask": "What types of cars do you want to buy?",
        "type": "multi",
        "options": [
            {"value": "trucks", "label": "Trucks"},
            {"value": "suvs", "label": "SUVs"},
            {"value": "sedans", "label": "Sedans"},
            {"value": "evs", "label": "Electric"},
            {"value": "any", "label": "Anything that fits", "recommended": True},
        ],
    },
    {
        "id": "price_band",
        "ask": "What price range?",
        "type": "single",
        "options": [
            {"value": "under_15k", "label": "Under $15k"},
            {"value": "15k_30k", "label": "$15k to $30k", "recommended": True},
            {"value": "30k_45k", "label": "$30k to $45k"},
            {"value": "over_45k", "label": "Over $45k"},
        ],
    },
    {
        "id": "max_miles",
        "ask": "Highest mileage you will take?",
        "type": "single",
        "options": [
            {"value": "80k", "label": "Under 80k miles"},
            {"value": "120k", "label": "Under 120k miles", "recommended": True},
            {"value": "any", "label": "Any mileage"},
        ],
    },
    {
        "id": "title_rule",
        "ask": "Which titles are OK?",
        "type": "single",
        "options": [
            {"value": "clean_only", "label": "Clean titles only", "recommended": True},
            {"value": "ask_first", "label": "Rebuilt too, but ask me first"},
        ],
    },
    {
        "id": "auctions",
        "ask": "Should the team bid at auctions for you?",
        "type": "single",
        "options": [
            {"value": "ask_each", "label": "Yes, ask me before each bid", "recommended": True},
            {"value": "auto_within_max", "label": "Yes, bid automatically within my max"},
            {"value": "no", "label": "No auctions"},
        ],
    },
    {
        "id": "approver",
        "ask": "Who approves buys and sales?",
        "type": "single",
        "options": [
            {"value": "me_text", "label": "Me, by text", "recommended": True},
            {"value": "me_dashboard", "label": "Me, in this dashboard"},
            {"value": "manager", "label": "My manager"},
        ],
    },
    {
        "id": "inventory",
        "ask": "How do you want to add your cars?",
        "type": "single",
        "options": [
            {"value": "upload", "label": "Upload a spreadsheet"},
            {"value": "forward", "label": "Send a list by text"},
            {"value": "later", "label": "Add them later", "recommended": True},
        ],
    },
]
