import { money, profit, time } from "./format";
import MoneyView from "./MoneyView";
import type { AgentEvent, Deal } from "./types";

// What the team did for the dealer: cars checked, bought, sold, and what needs a decision.
// Shared-brain and eval internals are not shown here.
const BOUGHT = ["bought", "in_transit", "delivered", "listed", "awaiting_sale", "sold"];
const ON_LOT = ["delivered", "listed", "awaiting_sale"];

export default function DealerInsights({ deals, events }: { deals: Deal[]; events: AgentEvent[] }) {
  const bought = deals.filter((d) => BOUGHT.includes(d.state));
  const sold = deals.filter((d) => d.state === "sold");
  const waiting = deals.filter((d) => d.state === "awaiting_approval" || d.state === "awaiting_sale").length;
  const onLot = deals.filter((d) => ON_LOT.includes(d.state)).length;
  const earned = sold.reduce((s, d) => s + (profit(d) ?? 0), 0);
  const belowAsk = bought.reduce((s, d) => s + Math.max(0, (d.asking ?? 0) - (d.bought_for ?? 0)), 0);
  const stopped = deals.filter((d) => d.state === "dropped").length;

  // Plain-language log of what the team did, newest first. Chat lines are left out.
  const activity = events.filter((e) => ["state", "approval", "blocked"].includes(e.type)).slice(-25).reverse();

  const stats: [string, string | number][] = [
    ["Cars checked", deals.length],
    ["Bought for you", bought.length],
    ["On the lot", onLot],
    ["Sold", sold.length],
    ["Profit from sold cars", money(earned)],
    ["Paid below asking", money(belowAsk)],
    ["Waiting for your OK", waiting],
    ["Passed on", stopped],
  ];

  return (
    <div className="stack">
      <section aria-label="Summary" className="summary">
        {stats.map(([label, value]) => (
          <div className="stat" key={label}>
            <span className="value">{value}</span>
            <span className="label">{label}</span>
          </div>
        ))}
      </section>

      <section className="stack-sm" aria-labelledby="money-head">
        <h2 id="money-head">Money per car</h2>
        <MoneyView deals={deals} />
      </section>

      <section className="stack-sm" aria-labelledby="work-head">
        <h2 id="work-head">What we did</h2>
        {activity.length === 0 ? (
          <p className="empty">Nothing yet. Start a shift and the work shows up here.</p>
        ) : (
          <ul className="log panel">
            {activity.map((e) => (
              <li key={e.id}>
                <span className="who">{time(e.ts)}</span>
                {e.text}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
