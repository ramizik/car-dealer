# Dealer / onboarding

**Job:** get a dealer set up in about two minutes. Dealers tap answers; the agent types nothing for them unless they choose to.

## Rules for the conversation

- **Multiple choice first.** Every question is a list of options (`backend/onboarding.py`). Never ask an open question when a list will do.
- **One question per screen or message.** Show the recommended option pre-selected, marked "Most dealers pick this".
- **Ask only what the team needs to act.** Eight questions, plus a phone number for approvals. Skip anything with a sensible default.
- **Free text only where a choice cannot work:** the approver's phone number and the inventory file itself.
- **Finish fast.** A dealer can press "Use recommended" then "Finish setup" and be live. Show progress ("Question 3 of 9").

## Questions (keep in sync with `backend/onboarding.py`)

1. Dealership type: independent lot, franchise, wholesale only.
2. What we do for them: buy cars, sell cars, or both (default both).
3. Final call: we find and negotiate and the dealer decides (default), or we act on our own within their limits.
4. Most we can spend on one car: $15k, $30k (default), $50k, $75k. Buying never offers above this.
5. Lowest profit per car when selling: $1,000, $1,500 (default), $2,500, $4,000. The sales desk caps what we pay so this profit is kept.
6. Car segments: premium, supercars, everyday (default), family and SUVs, or all of them.
7. Brands they sell (13 brands plus other).
8. Brands they want to buy (same list).
9. Where to list for sale: our website (default), Facebook Marketplace, Craigslist, Autotrader.
10. Car types to buy: trucks, SUVs, sedans, electric, anything (default).
11. Price range: under $15k, $15k to $30k (default), $30k to $45k, over $45k.
12. Highest mileage: under 80k, under 120k (default), any.
13. Titles: clean only (default), or rebuilt too but ask first.
14. Auctions: ask before each bid (default), bid automatically within max, or no auctions.
15. Who approves: me by text (default), me in this dashboard, my manager.
16. Adding cars: add later (default), upload a spreadsheet, send a list by text.

Then: approver phone number (only if they chose "me by text") and one authority tick: "Let the team list and bid within these choices."

## Save

`POST /onboarding/answers` writes each choice as a fact on `dealer-profile` in the brain (`backend/dealer_profile.py`), plus an `approval_policy` record that mirrors questions 3, 13, 14 and 15. Re-ask only when a choice is missing or older than 90 days.

## Rules

- Never post a listing or place a bid before the authority tick is recorded.
- Never store bank, card or government ID numbers. Those go through the dealer's own platform, never this chat.
- Every outbound message carries the AI-assistant disclosure line.
- Buying reads the profile: it skips if buying is off, and never offers above the per-car limit. The sales desk uses the dealer's minimum profit.
