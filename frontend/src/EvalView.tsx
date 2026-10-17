import type { EvalResult, EvalSide } from "./types";

type Props = { result: EvalResult | null };

const METRICS: { key: keyof EvalSide; name: string; unit: string; scale?: number; higher: boolean }[] = [
  { key: "close_rate", name: "Close rate", unit: "%", scale: 100, higher: true },
  { key: "mean_saved_pct", name: "Saved off asking", unit: "%", higher: true },
  { key: "surplus_captured_pct", name: "Seller surplus captured", unit: "%", higher: true },
  { key: "mean_rounds", name: "Rounds to close", unit: "", higher: false },
  { key: "scams_blocked", name: "Scams blocked", unit: "", higher: true },
  { key: "correct", name: "Correct calls", unit: "", higher: true },
];

// Real numbers from the last backend/eval.py run: same unseen sellers with the shared brain off, then on.
export default function EvalView({ result }: Props) {
  if (!result || result.missing || !result.on || !result.off) {
    return (
      <p className="empty-card">
        No measured run yet. In <code>backend</code>, run <code>SIM_FAST=1 python eval.py</code> and this page fills in.
      </p>
    );
  }
  const { on, off } = result;
  return (
    <>
      <p className="muted small">
        {result.heldout_n} sellers the team never met, run with the brain off, then on after {result.train_n} training deals.
        {result.ran_at ? ` Last run ${new Date(result.ran_at * 1000).toLocaleString("en-US")}.` : ""}
      </p>

      <section className="legend" aria-label="Key">
        <span><i className="swatch off" aria-hidden="true" />Brain off</span>
        <span><i className="swatch on" aria-hidden="true" />Brain on</span>
      </section>

      <section className="metrics">
        {METRICS.map((m) => {
          const a = Number(off[m.key]) * (m.scale ?? 1);
          const b = Number(on[m.key]) * (m.scale ?? 1);
          const max = Math.max(a, b) || 1;
          const delta = b - a;
          const better = m.higher ? delta > 0 : delta < 0;
          return (
            <div key={m.key} className="metric">
              <div className="row">
                <strong>{m.name}</strong>
                <span className={`mono small ${delta === 0 ? "muted" : better ? "good" : "bad"}`}>
                  {delta === 0 ? "no change" : `${delta > 0 ? "+" : ""}${Math.round(delta * 10) / 10}${m.unit}`}
                </span>
              </div>
              <Bar kind="off" value={a} max={max} unit={m.unit} label="Off" />
              <Bar kind="on" value={b} max={max} unit={m.unit} label="On" />
            </div>
          );
        })}
      </section>
    </>
  );
}

function Bar({ kind, value, max, unit, label }: { kind: "off" | "on"; value: number; max: number; unit: string; label: string }) {
  return (
    <div className="barrow">
      <span className="small muted" style={{ width: 40 }}>{label}</span>
      <div className={`bar ${kind}`} role="img" aria-label={`${label}: ${value}${unit}`}>
        <div style={{ width: `${(value / max) * 100}%` }} />
      </div>
      <span className="mono">{Math.round(value * 10) / 10}{unit}</span>
    </div>
  );
}
