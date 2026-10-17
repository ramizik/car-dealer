import type { Brain } from "./types";

const SCOPES: { key: keyof Brain["scopes"]; title: string; hint: string }[] = [
  { key: "dealer", title: "Your rules", hint: "What you told us you want" },
  { key: "parties", title: "Sellers & buyers", hint: "What we learned about people" },
  { key: "market", title: "Market", hint: "Prices, repairs, shipping, days to sell" },
  { key: "playbook", title: "What works", hint: "Tactics that win, by seller type" },
];

type Props = { brain: Brain; onSnapshot: (name: "cold" | "warm") => void };

export default function BrainView({ brain, onSnapshot }: Props) {
  const { stats } = brain;
  return (
    <>
      <section className="summary" aria-label="At a glance">
        <div className="stat"><span className="value">{stats.events}</span><span className="label">Things learned</span></div>
        <div className="stat"><span className="value">{stats.kb} KB</span><span className="label">Stored</span></div>
        <div className={`stat ${brain.conflicts.length ? "attn" : ""}`}>
          <span className="value">{brain.conflicts.length}</span>
          <span className="label">Disagreements to review</span>
        </div>
      </section>

      {stats.kb_before_compaction !== undefined && (
        <p className="muted small">
          Cleaned up automatically: {stats.kb_before_compaction} KB down to {stats.kb} KB.
        </p>
      )}

      <section className="cards4" aria-label="What we know">
        {SCOPES.map((s) => (
          <div key={s.key} className="scope">
            <h3>{s.title}</h3>
            <p className="small">{s.hint}</p>
            {brain.scopes[s.key].length === 0 && <p className="empty">Nothing learned yet</p>}
            <ul className="facts">
              {brain.scopes[s.key].map((f) => <li key={f}>{f}</li>)}
            </ul>
          </div>
        ))}
      </section>

      <section aria-labelledby="tactics">
        <h2 id="tactics">Negotiation tactics</h2>
        <p className="muted small">How often each approach closed a deal, by seller type.</p>
        <table>
          <thead>
            <tr><th>Tactic</th><th>Seller type</th><th>Won</th><th>Win rate</th></tr>
          </thead>
          <tbody>
            {brain.playbook.map((p) => {
              const rate = p.tries ? p.wins / p.tries : 0;
              return (
                <tr key={p.tactic + p.segment}>
                  <td>{p.tactic.replace(/_/g, " ")}</td>
                  <td>{p.segment.replace(/_/g, " ")}</td>
                  <td>{p.wins} of {p.tries}</td>
                  <td>
                    <div className="row">
                      <div className="bar" role="img" aria-label={`${Math.round(rate * 100)}% win rate`}>
                        <div style={{ width: `${rate * 100}%` }} />
                      </div>
                      <span className="small">{Math.round(rate * 100)}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {brain.conflicts.length > 0 && (
        <section aria-labelledby="disagree">
          <h2 id="disagree">Disagreements</h2>
          <p className="muted small">We have two different answers for these. We use the more reliable one until you review it.</p>
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

      <section className="row" aria-label="Demo controls">
        <span className="muted small">Demo</span>
        <button onClick={() => onSnapshot("cold")}>Start empty</button>
        <button onClick={() => onSnapshot("warm")}>Load past deals</button>
      </section>
    </>
  );
}
