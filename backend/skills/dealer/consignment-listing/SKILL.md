# Dealer / consignment listing

**Job:** list a dealer's approved inventory on the platforms they chose, handle buyer enquiries on those listings, and report sales back to the dealer. We act as the dealer's sales desk.

## Steps

1. Read own skill + top `MISTAKES.md` lines. Read `shared/sales-playbook`.
2. `brain.recall` for `dealer:{id}` (sell policy, fee, floor rules) and the make/model segment (days-to-sell, comps).
3. Check the car: VIN, title status, photos, and that the dealer's `approval_policy` allows posting. Missing item → `needs_info` to the dealer, no post.
4. Build one listing pack from the dealer's data only: title, year/make/model/trim, miles, VIN, title status, known issues, photos, price, disclosure line, dealer name and contact for approvals.
5. Clone per platform the dealer selected (storefront, FB-style, Craigslist-style, Autotrader-style). Change length and headline only. Never change price or facts per platform.
6. Price: list at or above the dealer's `floor`. Any change below floor, or a sale commitment, goes to the dealer as an `approval_request`.
7. Route each enquiry to the seller enquiry agent under that dealer's profile. Keep the dealer's floor and buyer data private.
8. On a sale: write `sale` (price, fee, margin to the dealer), send the dealer a summary, and release the listing from all platforms.
9. On a miss (listing removed, wrong fact corrected by a buyer, dealer rejects a price), add one dated line to own `MISTAKES.md`.

## Rules

- No listing without a recorded dealer authority answer and a VIN.
- Title status and accidents are always stated. Hiding them is a miss.
- Fee and commission are shown to the dealer before the first listing goes live.
- Hackathon build: channel cards and the storefront are simulated; no real platform posts.
