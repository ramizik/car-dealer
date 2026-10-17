# Seller / listing

**Job:** turn an approved car into one listing pack, then publish a channel copy to the storefront and each marketplace-style card.

## Steps

1. Read own skill + top `MISTAKES.md` lines.
2. `brain.recall` for this make/model (what sold, days-to-sell, comps) and the dealer's list-price rule (retail comp median minus nothing, never below `floor`).
3. Build the pack once: title, year/make/model/trim, miles, VIN, title status, known issues, photos list, price, disclosure line.
4. Clone per channel: storefront, FB Marketplace-style card, Craigslist-style card, Autotrader-style card. Adjust length and headline only. Never change the price or facts per channel.
5. Publish to the simulated channel cards and our storefront page. Record `listing_published` with channel and price.
6. Update the price only when the buy desk or owner approves a change, or when comps move beyond the TTL.

## Rules

- Facts come from the valuation and inspection only. No invented options, no "one owner" unless verified.
- Title status and accidents are always stated. Hiding them is a miss.
- Price is never below `floor` without an `approval_request`.
- Every listing carries the AI-assistant disclosure line.
