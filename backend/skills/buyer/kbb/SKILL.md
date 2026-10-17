# Buyer / KBB valuation

**Job:** value a candidate car from book comps and set `max_buy`. You do not talk to anyone here.

## Steps

1. Read own skill + top `MISTAKES.md` lines.
2. `brain.recall` for this make/model/year segment (recent `market` observations, `playbook` stats).
3. You.com **Research** for a cited valuation: retail range, trade range, typical mileage adjustment. Keep source URLs.
4. Adjust for miles, title (clean only), accidents, known issues. Write each adjustment as a line in the valuation.
5. `max_buy = min(0.92 * retail_comp_median, retail_comp_median - target_gross)`, using the dealer target gross (12-15%).
6. Reject automatically if: title not clean, miles over 120k, comps fewer than 3, or comps older than the TTL.
7. Write `market` observations (price, source, date) and the `max_buy` decision.

## Output

`{car_id, comps:[{price, miles, source_url}], retail_median, max_buy, verdict: buy_candidate|reject, reasons[]}`

## Rules

- Never guess a comp. If Research returns fewer than 3 cited comps, say so and return `needs_more_data`.
- Cache by segment for the TTL, so the demo does not hit You.com every tick.
- `max_buy` is clamped before any offer leaves the system.
