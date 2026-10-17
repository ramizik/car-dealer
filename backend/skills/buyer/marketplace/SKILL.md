# Buyer / marketplace watch

**Job:** keep searching public listings (Facebook Marketplace, Craigslist, Autotrader-style, auctions) for cars that fit the lot profile, and hand matches to the buy outreach agent.

## Steps

1. Read own skill + top `MISTAKES.md` lines.
2. `brain.recall` for the lot profile (makes, price band $8k-$45k, miles under 120k, clean title only) and recently rejected listings.
3. You.com **Search** with a site-scoped query per source, then **Contents** for the top hits. Dedupe by URL and by VIN/title+price.
4. Pre-filter: price in band, title not salvage or rebuilt, not already seen, source on the allowlist.
5. For each survivor, call the KBB buyer for `max_buy`. Keep it only if the listing ask is at or under `max_buy` plus a small margin for negotiation.
6. Write one `listing_seen` event per URL (source, ask, miles, title status) and a source-quality counter (matches per query).
7. Hand off to `buyer/outreach` with `{listing_url, ask, max_buy}`.

## Rules

- Read listings only. Never log in, never post, never click payment or "verify" links. An off-allowlist link is recorded and skipped.
- If a source returns nothing for 3 ticks, back off and log it. Do not scrape sites that block bots.
- Cap the feed at the lean limit (for example 20 active matches per shift).
