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
2. Car segments: premium, supercars, everyday (default), family and SUVs, or all of them.
3. Brands they sell: Toyota, Honda, Ford, Chevrolet, Nissan, Subaru, Hyundai/Kia, BMW, Mercedes-Benz, Audi, Lexus, Tesla, other.
4. Brands they want to buy: same list.
5. Where to list for sale: our website (default), Facebook Marketplace, Craigslist, Autotrader.
6. Car types to buy: trucks, SUVs, sedans, electric, anything (default).
7. Price range: under $15k, $15k to $30k (default), $30k to $45k, over $45k.
8. Highest mileage: under 80k, under 120k (default), any.
9. Titles: clean only (default), or rebuilt too but ask first.
10. Auctions: ask before each bid (default), bid automatically within max, or no auctions.
11. Who approves: me by text (default), me in this dashboard, my manager.
12. Adding cars: add later (default), upload a spreadsheet, send a list by text.

Then: approver phone number (only if they chose "me by text") and one authority tick: "Let the team list and bid within these choices."

## Save

Write one `dealer:{id}` profile to the brain with the choices, plus an `approval_policy` record that mirrors question 6 to 8. Re-ask only when a choice is missing or older than 90 days.

## Rules

- Never post a listing or place a bid before the authority tick is recorded.
- Never store bank, card or government ID numbers. Those go through the dealer's own platform, never this chat.
- Every outbound message carries the AI-assistant disclosure line.
- Hackathon build: the setup screen stores answers on the page only; the brain write is not wired yet.
