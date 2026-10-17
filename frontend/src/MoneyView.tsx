import { money, profit, stageLabel } from "./format";
import type { Deal } from "./types";

const BOUGHT = ["bought", "in_transit", "delivered", "listed", "sold"];
const signed = (n?: number) => (n === undefined ? "—" : `${n < 0 ? "-" : "+"}${money(Math.abs(n))}`);
const pct = (n: number, base?: number) => (base ? ` (${n < 0 ? "" : "+"}${((n / base) * 100).toFixed(1)}%)` : "");

// Expected profit if a listed car sells at its list price; real profit once sold.
const expected = (d: Deal) =>
  d.state === "sold" ? profit(d) : d.state === "listed" && d.list_price !== undefined && d.bought_for !== undefined ? d.list_price - d.bought_for : undefined;

export default function MoneyView({ deals }: { deals: Deal[] }) {
  const sold = deals.filter((d) => d.state === "sold");
  const listed = deals.filter((d) => d.state === "listed");
  const owned = deals.filter((d) => BOUGHT.includes(d.state) && d.state !== "sold");
  const earned = sold.reduce((s, d) => s + (profit(d) ?? 0), 0);
  const pipeline = listed.reduce((s, d) => s + (expected(d) ?? 0), 0);
  const tied = owned.reduce((s, d) => s + (d.bought_for ?? 0), 0);
  const wins = sold.filter((d) => (profit(d) ?? 0) > 0).length;
  const avg = sold.length ? earned / sold.length : undefined;
  const rows = deals.filter((d) => BOUGHT.includes(d.state)).sort((a, b) => (expected(b) ?? -1e9) - (expected(a) ?? -1e9));
  const best = sold.length ? sold.reduce((a, b) => ((profit(b) ?? 0) > (profit(a) ?? 0) ? b : a)) : undefined;

  return (
    <div className="stack">
      <div className="kpis">
        <div className="kpi"><div className="value">{signed(earned)}</div><div className="label">Made so far ({sold.length} sold)</div></div>
        <div className="kpi"><div className="value">{signed(pipeline)}</div><div className="label">Expected from {listed.length} listed</div></div>
        <div className="kpi"><div className="value">{avg === undefined ? "—" : signed(avg)}</div><div className="label">Average per sold car</div></div>
        <div className="kpi"><div className="value">{money(tied)}</div><div className="label">Cash in cars not yet sold</div></div>
      </div>
      <p className="muted small">
        {sold.length ? `${wins} of ${sold.length} sold cars made money.` : "No sales yet."}
        {best && ` Best so far: ${best.car.split(" · ")[0]} ${signed(profit(best))}.`} Profit is sale price minus purchase price, before reconditioning and fees.
      </p>
      <table>
        <thead>
          <tr><th>Car</th><th>Status</th><th>Paid</th><th>Sold / listed</th><th>Profit</th></tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={5} className="empty">No purchases yet. Profit shows here once we buy a car.</td></tr>}
          {rows.map((d) => {
            const p = expected(d);
            const final = d.state === "sold";
            return (
              <tr key={d.id}>
                <td>{d.car.split(" · ")[0]}</td>
                <td>{stageLabel(d.state)}</td>
                <td>{money(d.bought_for)}</td>
                <td>{money(d.sold_for ?? d.list_price)}</td>
                <td style={{ fontWeight: 650, color: p === undefined ? undefined : p < 0 ? "var(--danger)" : "var(--ok)" }}>
                  {p === undefined ? "Not priced yet" : `${signed(p)}${pct(p, d.bought_for)}${final ? "" : " expected"}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
