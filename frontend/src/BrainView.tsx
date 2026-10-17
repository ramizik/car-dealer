import type { Brain } from "./types";

const SCOPES: { key: keyof Brain["scopes"]; title: string; hint: string }[] = [
  { key: "dealer", title: "Your rules", hint: "What you told us you want" },
  { key: "parties", title: "Sellers & buyers", hint: "What we learned about people" },
  { key: "market", title: "Market", hint: "Prices, recon, shipping, days to sell" },
  { key: "playbook", title: "What works", hint: "Tactics that win, per seller type" },
];

type Props = { brain: Brain; onSnapshot: (name: "cold" | "warm") => void };

export default function BrainView({ brain, onSnapshot }: Props) {
  const { stats } = brain;
  return (
    <div className="stack">
      <p className="lede">
        Every agent reads this memory before it acts and adds to it after. It is shared across the whole team.
      </p>

      <section className="summary">
        <div className="stat"><span className="value">{stats.events}</span><span className="muted">Things learned</span></div>
        <div className="stat"><span className="value">{stats.kb} KB</span><span className="muted">Memory size</span></div>
        {stats.kb_before_compaction !== undefined && (
          <div className="stat">
            <span className="value">−{Math.round((1 - stats.kb / stats.kb_before_compaction) * 100)}%</span>
            <span className="muted">After cleanup ({stats.kb_before_compaction} → {stats.kb} KB)</span>
          </div>
        )}
        <div className={`stat ${brain.conflicts.length ? "warn" : ""}`}>
          <span className="value">{brain.conflicts.length}</span><span className="muted">Disagreements</span>
        </div>
      </section>

      <section className="grid4">
        {SCOPES.map((s) => (
          <div key={s.key} className="column">
            <h3 title={s.hint}>{s.title}</h3>
            <p className="muted small">{s.hint}</p>
            {brain.scopes[s.key].length === 0 && <p className="empty">Nothing learned yet</p>}
            <ul className="facts">
              {brain.scopes[s.key].map((f) => <li key={f}>{f}</li>)}
            </ul>
          </div>
        ))}
      </section>

      <section>
        <h2>Negotiation tactics</h2>
        <table>
          <thead>
            <tr><th>Tactic</th><th>Seller type</th><th>Won</th><th className="wide">Win rate</th></tr>
          </thead>
          <tbody>
            {brain.playbook.map((p) => {
              const rate = p.tries ? p.wins / p.tries : 0;
              return (
                <tr key={p.tactic + p.segment}>
                  <td>{p.tactic.replace(/_/g, " ")}</td>
                  <td>{p.segment.replace(/_/g, " ")}</td>
                  <td>{p.wins}/{p.tries}</td>
                  <td><div className="bar"><div style={{ width: `${rate * 100}%` }} /></div></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {brain.conflicts.length > 0 && (
        <section>
          <h2>Disagreements</h2>
          <p className="muted small">Two agents saved different answers. The higher-confidence one is used until resolved.</p>
          {brain.conflicts.map((c) => (
            <div key={c.key} className="conflict">
              <strong>{c.key}</strong>
              <span>{c.a}</span>
              <span className="muted">vs</span>
              <span>{c.b}</span>
            </div>
          ))}
        </section>
      )}

      <section className="row">
        <span className="muted small">Demo memory:</span>
        <button onClick={() => onSnapshot("cold")}>Start empty</button>
        <button onClick={() => onSnapshot("warm")}>Load trained</button>
      </section>
    </div>
  );
}
