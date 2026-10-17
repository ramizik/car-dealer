import { COLUMNS, keyNumber, money, profit, stageLabel, time } from "./format";
import type { AgentEvent, Deal } from "./types";

type Props = {
  deals: Deal[];
  events: AgentEvent[];
  onOpen: (id: string) => void;
  onDecide: (id: string, yes: boolean) => void;
};

export default function ShiftView({ deals, events, onOpen, onDecide }: Props) {
  const waiting = deals.filter((d) => d.state === "awaiting_approval");
  const stopped = deals.filter((d) => d.state === "dropped");
  const earned = deals.reduce((sum, d) => sum + (profit(d) ?? 0), 0);

  return (
    <div className="shift">
      <main>
        <section className="summary">
          <Stat label="Needs your OK" value={waiting.length} tone={waiting.length ? "warn" : undefined} />
          <Stat label="Buying" value={count(deals, COLUMNS[0].states)} />
          <Stat label="In stock" value={count(deals, [...COLUMNS[1].states, ...COLUMNS[2].states])} />
          <Stat label="Profit closed" value={money(earned)} />
        </section>

        {waiting.length > 0 && (
          <section>
            <h2>Needs your OK</h2>
            {waiting.map((d) => (
              <div key={d.id} className="approval">
                <div>
                  <strong>
                    Buy {d.car.split(" · ")[0]} for {money(d.offer)}?
                  </strong>
                  <p className="muted">
                    Your max {money(d.max_buy)} · Asking {money(d.asking)} · Est. retail {money(d.valuation?.mid)}
                  </p>
                </div>
                <div className="actions">
                  <button className="link" onClick={() => onOpen(d.id)}>Details</button>
                  <button onClick={() => onDecide(d.id, false)}>Decline</button>
                  <button className="primary" onClick={() => onDecide(d.id, true)}>Approve</button>
                </div>
              </div>
            ))}
          </section>
        )}

        <section className="board">
          {COLUMNS.map((col) => {
            const cards = deals.filter((d) => col.states.includes(d.state));
            return (
              <div key={col.title} className="column">
                <h3 title={col.hint}>
                  {col.title} <span className="muted">{cards.length}</span>
                </h3>
                {cards.length === 0 && <p className="empty">Nothing here yet</p>}
                {cards.map((d) => (
                  <button key={d.id} className="card" onClick={() => onOpen(d.id)}>
                    <span className="car">{d.car}</span>
                    <span className="muted">{d.location}</span>
                    <span className="row">
                      <span className={`pill ${d.state === "awaiting_approval" ? "warn" : ""}`}>{stageLabel(d.state)}</span>
                      <span>{keyNumber(d)}</span>
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </section>

        {stopped.length > 0 && (
          <section>
            <h2>Stopped</h2>
            {stopped.map((d) => (
              <button key={d.id} className="stopped" onClick={() => onOpen(d.id)}>
                <span>{d.car}</span>
                <span className="muted">{d.drop_reason}</span>
              </button>
            ))}
          </section>
        )}
      </main>

      <aside className="feed">
        <h2>Activity</h2>
        {events.length === 0 && <p className="empty">No activity yet. Start a shift.</p>}
        <ol>
          {[...events].reverse().map((e) => (
            <li key={e.id} className={e.type === "blocked" ? "blocked" : e.type === "approval" ? "warn" : ""}>
              <span className="muted">
                {time(e.ts)} · {e.agent}
                {e.deal_id && ` · ${e.deal_id}`}
              </span>
              <span>{e.text}</span>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: "warn" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <span className="value">{value}</span>
      <span className="muted">{label}</span>
    </div>
  );
}

const count = (deals: Deal[], states: Deal["state"][]) => deals.filter((d) => states.includes(d.state)).length;
