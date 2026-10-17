import { STAGES, money, profit, time } from "./format";
import type { AgentEvent, Deal } from "./types";

type Props = {
  deal: Deal;
  events: AgentEvent[];
  onClose: () => void;
  onDecide: (id: string, yes: boolean) => void;
};

export default function DealPanel({ deal, events, onClose, onDecide }: Props) {
  const step = STAGES.findIndex((s) => s.state === deal.state);
  const history = events.filter((e) => e.deal_id === deal.id);

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="panel" onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <span className="muted">{deal.id} · {deal.location}</span>
            <h2>{deal.car}</h2>
          </div>
          <button className="link" onClick={onClose} aria-label="Close">Close</button>
        </header>

        {deal.state === "dropped" ? (
          <p className="notice blocked">Stopped: {deal.drop_reason}</p>
        ) : (
          <ol className="steps">
            {STAGES.map((s, i) => (
              <li key={s.state} className={i < step ? "done" : i === step ? "now" : ""}>{s.label}</li>
            ))}
          </ol>
        )}

        {deal.state === "awaiting_approval" && (
          <div className="approval">
            <strong>Buy for {money(deal.offer)}?</strong>
            <div className="actions">
              <button onClick={() => onDecide(deal.id, false)}>Decline</button>
              <button className="primary" onClick={() => onDecide(deal.id, true)}>Approve</button>
            </div>
          </div>
        )}

        <dl className="numbers">
          <Num label="Asking" value={money(deal.asking)} />
          <Num label="Your max" value={money(deal.max_buy)} />
          <Num label="Our offer" value={money(deal.offer)} />
          <Num label="Paid" value={money(deal.bought_for)} />
          <Num label="Listed at" value={money(deal.list_price)} />
          <Num label="Profit" value={money(profit(deal))} />
        </dl>

        {deal.valuation && (
          <section>
            <h3>Market value</h3>
            <p>
              {money(deal.valuation.low)} – {money(deal.valuation.high)}, most likely <strong>{money(deal.valuation.mid)}</strong>
            </p>
            <ul className="sources">
              {deal.valuation.citations.map((c) => (
                <li key={c.url}>
                  <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {deal.chat.length > 0 && (
          <section>
            <h3>Conversation</h3>
            <div className="chat">
              {deal.chat.map((t, i) => (
                <div key={i} className={`bubble ${t.from === "agent" ? "ours" : ""}`}>
                  <span className="muted">{t.from === "agent" ? `Our agent${t.tactic ? ` · ${t.tactic.replace(/_/g, " ")}` : ""}` : "Seller"}</span>
                  <p>{t.text}</p>
                  {t.recalled && t.recalled.length > 0 && (
                    <div className="chips" title="What the agent pulled from shared memory before writing this">
                      <span className="muted">Used memory:</span>
                      {t.recalled.map((r) => <span key={r} className="chip">{r}</span>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3>History</h3>
          {history.length === 0 && <p className="empty">No events for this car yet</p>}
          <ol className="history">
            {history.map((e) => (
              <li key={e.id} className={e.type === "blocked" ? "blocked" : ""}>
                <span className="muted">{time(e.ts)} · {e.agent}</span> {e.text}
              </li>
            ))}
          </ol>
        </section>

      </aside>
    </div>
  );
}

function Num({ label, value }: { label: string; value: string }) {
  if (value === "—") return null;
  return (
    <div>
      <dt className="muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
