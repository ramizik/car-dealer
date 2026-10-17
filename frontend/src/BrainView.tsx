import type { Brain, BrainEntry } from "./types";

const SCOPES: { key: keyof Brain["scopes"]; title: string; hint: string }[] = [
  { key: "dealer", title: "Your rules", hint: "What you told us and decided" },
  { key: "party", title: "Sellers and buyers", hint: "What we learned about people" },
  { key: "market", title: "Market", hint: "Prices, values, days to sell" },
  { key: "playbook", title: "What works", hint: "Tactic wins by seller type" },
];

const fmt = (v: unknown) =>
  typeof v === "number"
    ? Math.abs(v) >= 1000 ? `$${Math.round(v).toLocaleString("en-US")}` : String(Math.round(v * 100) / 100)
    : typeof v === "string" ? v : JSON.stringify(v);

// One readable line per fact, observation, counter and note in a brain entry.
function lines(e: BrainEntry): string[] {
  const out: string[] = [];
  for (const [a, f] of Object.entries(e.facts)) out.push(`${a}: ${fmt(f.value)}`);
  for (const [a, o] of Object.entries(e.obs)) out.push(`${a} median ${fmt(o.median)} (n=${o.n})`);
  for (const [a, c] of Object.entries(e.counters)) {
    const t = c as { tries?: number; wins?: number };
    out.push(t && typeof t === "object" && "tries" in t ? `won ${t.wins ?? 0} of ${t.tries}` : `${a}: ${fmt(c)}`);
  }
  for (const n of e.notes.slice(-2)) out.push(n.private_to ? `(private to ${n.private_to.join(", ")}) ${n.text}` : n.text);
  return out;
}

type Props = { brain: Brain | null; onSnapshot: (name: "cold" | "warm") => void };

export default function BrainView({ brain, onSnapshot }: Props) {
  if (!brain) return <p className="empty-card">Can't reach the backend, so the shared brain can't be shown.</p>;
  const { stats } = brain;
  return (
    <>
      <section className="stats" aria-label="At a glance">
        <div className="stat2"><span className="v mono">{stats.events}</span><span className="l">Memory writes, all time</span></div>
        <div className="stat2"><span className="v mono">{Math.round(stats.bytes / 1024)} KB</span><span className="l">Stored on disk</span></div>
        <div className="stat2"><span className="v mono">{Object.values(stats.keys).reduce((a, b) => a + b, 0)}</span><span className="l">Distinct topics</span></div>
        <div className="stat2"><span className={`v mono ${stats.conflicts ? "bad" : ""}`}>{stats.conflicts}</span><span className="l">Conflicts resolved</span></div>
      </section>

      {brain.tiers && (
        <section className="cards4" aria-label="Memory layers">
          <div className="scope">
            <h3>1. Private chats</h3>
            <p className="small">Raw talk, one file per seller. Only the agent who had the chat reads it.</p>
            <span className="v mono">{brain.tiers.private_chats}</span> <span className="small muted">conversations</span>
            <p className="small muted">{brain.tiers.private_writes} private gists in the brain</p>
          </div>
          <div className="scope">
            <h3>2. Shared brain</h3>
            <p className="small">One result line per deal. Every agent reads it before work.</p>
            <span className="v mono">{brain.tiers.shared_writes}</span> <span className="small muted">shared writes</span>
          </div>
          <div className="scope">
            <h3>3. Lessons</h3>
            <p className="small">Distilled by the librarian every 3 deals.</p>
            {brain.tiers.lessons.length === 0 ? <p className="empty">None yet</p> :
              brain.tiers.lessons.map((l) => <span key={l} className="small fact-line">{l.replace(/^lesson: /, "")}</span>)}
          </div>
          <div className="scope">
            <h3>Known mistakes</h3>
            <p className="small">Repeated misses. Top lines go into the negotiator's prompt.</p>
            {brain.tiers.mistakes.length === 0 ? <p className="empty">None yet</p> :
              brain.tiers.mistakes.map((m) => <span key={m} className="small fact-line">{m.replace(/^- \d{4}-\d{2}-\d{2} /, "")}</span>)}
          </div>
        </section>
      )}

      <section className="cards4" aria-label="What we know">
        {SCOPES.map((s) => {
          const entries = Object.entries(brain.scopes[s.key] ?? {}).sort((a, b) => b[1].ts - a[1].ts);
          return (
            <div key={s.key} className="scope">
              <h3>{s.title}</h3>
              <p className="small">{s.hint} · {stats.per_scope[s.key] ?? 0} writes</p>
              {entries.length === 0 && <p className="empty">Nothing learned yet</p>}
              <ul className="facts">
                {entries.slice(0, 6).map(([k, e]) => (
                  <li key={k}>
                    <strong className="small">{k.replace(/\|/g, " @ ")}</strong>
                    {lines(e).slice(0, 2).map((l) => <span key={l} className="small muted fact-line">{l}</span>)}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>

      <section aria-labelledby="tactics">
        <h2 id="tactics">Negotiation tactics</h2>
        <p className="muted small">How often each approach closed a deal, by seller type. The negotiator reads this before every talk.</p>
        {brain.playbook.length === 0 ? (
          <p className="empty">No tactic results yet.</p>
        ) : (
          <table>
            <thead><tr><th>Tactic</th><th>Seller type</th><th className="num">Won</th><th className="num">Win rate</th></tr></thead>
            <tbody>
              {brain.playbook.map((p) => (
                <tr key={p.tactic + p.segment}>
                  <td>{p.tactic.replace(/_/g, " ")}</td>
                  <td>{p.segment.replace(/_/g, " ")}</td>
                  <td className="num mono">{p.wins} of {p.tries}</td>
                  <td className="num mono">{Math.round((p.tries ? p.wins / p.tries : 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {brain.conflicts.length > 0 && (
        <section aria-labelledby="disagree">
          <h2 id="disagree">Conflicts</h2>
          <p className="muted small">Two agents wrote different confident answers. The brain keeps the higher-confidence one.</p>
          {brain.conflicts.map((c) => (
            <div key={c.scope + c.key + c.attr} className="conflict">
              <strong>{c.scope} / {c.key} / {c.attr}</strong>
              <span>{c.values.join(" vs ")}</span>
              <span className="muted">kept {fmt(c.chosen)}</span>
            </div>
          ))}
        </section>
      )}

      <section className="row" aria-label="Brain snapshots">
        <span className="muted small">Snapshots</span>
        <button onClick={() => onSnapshot("cold")}>Load empty brain</button>
        <button onClick={() => onSnapshot("warm")}>Load trained brain</button>
      </section>
    </>
  );
}
