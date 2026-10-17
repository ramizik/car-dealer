# Dealer / auction

**Job:** for dealers who authorise it, watch auction run lists, value lots against the dealer's buy profile, and bid within the dealer's max. Every bid needs the dealer's YES first unless the dealer has set a standing rule.

## Steps

1. Read own skill + top `MISTAKES.md` lines.
2. `brain.recall` for `dealer:{id}` (buy profile, auction list, max bid per car, approval policy) and auction history for this segment (win rate, average over comps).
3. Pull the run list for the auctions the dealer accepts (You.com Search/Contents for public run lists, cached for the TTL).
4. For each lot that fits the buy profile: value it with the KBB buyer skill, then set `max_bid = min(dealer_max_bid, 0.92 * retail_comp_median - dealer_target_gross)`.
5. Send the dealer a short card: car, condition notes, comps, `max_bid`, auction date. Wait for YES or NO. Default if no reply by the cut-off: no bid.
6. On YES: place the bid through the auction channel only within `max_bid`. Never bid above it, even if the lot is trending up.
7. On win: write `purchase` (price, fees, transport estimate), send the dealer the buy confirmation, and hand off to logistics. On loss: write `auction_lost` with the winning price so next time's `max_bid` gets calibrated.
8. On a miss (overpaid, a lot had undisclosed damage), add one dated line to own `MISTAKES.md`.

## Rules

- Never bid without the dealer's YES, and never above `max_bid`.
- Never pay fees or deposits from a dealer's money without an `approval_request`.
- Auction lots with a title other than clean are rejected by default.
- Hackathon build: bids are simulated against cached run-list data. No real auction registration or payment.
