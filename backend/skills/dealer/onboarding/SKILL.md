# Dealer / onboarding

**Job:** a dealer who comes to us sets up a profile so we can sell their inventory, buy for them, and bid in auctions on their behalf. Runs once per dealer, then on change.

## Ask the dealer (one question per message, save each answer)

1. **Identity:** legal name, dealer licence number, city and state, contact for approvals (name, phone or Telegram).
2. **Sell side:** which of their cars we may list, and on which platforms (storefront, Facebook Marketplace-style, Craigslist-style, Autotrader-style). Commission or fee per sale.
3. **Buy side:** makes and models wanted, price band, mileage cap, title rule (clean only by default), max gross margin target.
4. **Auctions:** which auctions they accept us bidding at, a max bid per car, and whether a bid needs their YES first (default: yes).
5. **Approvals:** what needs their YES (every buy, every sale below floor, every bid, every posting). Default: all of them.
6. **Inventory:** upload or paste the list (VIN, year, make, model, miles, asking price, floor, photos, title status, known issues). Missing VIN or title status blocks listing.
7. **Authority:** confirm they authorise us to post their listings and to bid on their behalf within the rules above. Record the date and their words.

## Save

Write one `dealer:{id}` profile to the brain with the answers, and an `approval_policy` record. Re-ask only fields that are missing or older than 90 days.

## Rules

- Never post a listing or place a bid before the authority answer (step 7) is recorded.
- Never store bank, card or government ID numbers. Ask for them only through the dealer's own platform, never in chat.
- Every outbound message carries the AI-assistant disclosure line.
- Hackathon build: profile, listings and bids run on the simulator and cached listing text. Real postings or bids are out of scope until the dealer has signed up on each platform themselves.
