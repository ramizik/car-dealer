import { useState } from "react";
import { COLUMNS, keyNumber, money, profit, stageLabel, time } from "./format";
import type { AgentEvent, Deal } from "./types";

type Props = {
  deals: Deal[];
  events: AgentEvent[];
  running: boolean;
  onOpen: (id: string) => void;
  onDecide: (id: string, yes: boolean) => void;
};

const AGENT_NAMES: Record<string, string> = {
  scout: "Scout",
  appraiser: "Valuer",
  negotiator: "Negotiator",
  seller: "Seller",
  seller_agent: "Sales desk",
  logistics: "Shipping",
  librarian: "Memory",
};

export default function ShiftView({ deals, events, running, onOpen, onDecide }: Props) {
  const [onlyAttention, setOnlyAttention] = useState(false);
  const waiting = deals.filter((d) => d.state === "awaiting_approval");
  const stopped = deals.filter((d) => d.state === "dropped");
  const earned = deals.reduce((sum, d) => sum + (profit(d) ?? 0), 0);
  const buying = count(deals, COLUMNS[0].states);
  const onTheWay = count(deals, [...COLUMNS[1].states, ...COLUMNS[2].states]);

  const feed = [...events].reverse();
  const attention = feed.filter((e) => e.type === "blocked" || e.type === "approval" || e.type === "error");
  const shown = onlyAttention ? attention : feed;

  return (
    <div className="stack">
      <section className={`hero ${waiting.length ? "attn" : ""}`}>
        <h1>{heading(waiting.length, running)}</h1>
        <p>{subheading(waiting.length, running)}</p>
      </section>

      <section className="summary" aria-label="Today at a glance">
        <div className="stat"><span className="value">{buying}</span><span className="label">Being looked at</span></div>
        <div className="stat"><span className="value">{onTheWay}</span><span className="label">Bought or for sale</span></div>
        <div className="stat"><span className="value">{money(earned)}</span><span className="label">Profit so far</span></div>
      </section>

      {waiting.length > 0 && (
        <section aria-labelledby="needs-ok">
          <div className="section-head">
            <h2 id="needs-ok">Waiting for you</h2>
            <span className="muted small">Nothing is bought until you say yes</span>
          </div>
          <div className="decisions">
            {waiting.map((d) => (
              <article key={d.id} className="decision">
                <div>
                  <h3>Buy {d.car.split(" · ")[0]}</h3>
                  <p>
                    Offer {money(d.offer)} is under your max of {money(d.max_buy)}. Asking {money(d.asking)}, market value about {money(d.valuation?.mid)}.
                  </p>
                </div>
                <div className="actions">
                  <button className="quiet" onClick={() => onOpen(d.id)}>See details</button>
                  <button onClick={() => onDecide(d.id, false)}>Decline</button>
                  <button className="primary" onClick={() => onDecide(d.id, true)}>Approve {money(d.offer)}</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <div className="layout">
        <div className="stack">
          <section aria-labelledby="pipeline">
            <div className="section-head">
              <h2 id="pipeline">Pipeline</h2>
            </div>
            <div className="board">
              {COLUMNS.map((col) => {
                const cards = deals.filter((d) => col.states.includes(d.state));
                return (
                  <div key={col.title} className="column">
                    <header>
                      <h3>
                        {col.title} <span className="muted">· {cards.length}</span>
                      </h3>
                      <p>{col.hint}</p>
                    </header>
                    {cards.length === 0 && <p className="empty">Nothing here yet</p>}
                    {cards.map((d) => (
                      <button key={d.id} className="card" onClick={() => onOpen(d.id)} aria-label={`${d.car}, ${stageLabel(d.state)}. Open details`}>
                        <span className="car">{d.car}</span>
                        <span className="meta">{d.location}</span>
                        <span className="foot">
                          <span className={`pill ${d.state === "awaiting_approval" ? "attn" : ""}`}>{stageLabel(d.state)}</span>
                          <span>{keyNumber(d)}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          </section>

          {stopped.length > 0 && (
            <details className="stopped">
              <summary>Stopped ({stopped.length})</summary>
              {stopped.map((d) => (
                <button key={d.id} className="card" onClick={() => onOpen(d.id)}>
                  <span className="car">{d.car}</span>
                  <span className="meta">{d.drop_reason}</span>
                </button>
              ))}
            </details>
          )}
        </div>

        <aside className="feed" aria-labelledby="activity">
          <div className="feed-head">
            <h2 id="activity">What the team did</h2>
            <div className="filters">
              <button aria-pressed={!onlyAttention} onClick={() => setOnlyAttention(false)}>All</button>
              <button aria-pressed={onlyAttention} onClick={() => setOnlyAttention(true)}>Needs attention</button>
            </div>
          </div>
          {shown.length === 0 && (
            <p className="empty">{events.length === 0 ? "No activity yet. Start today's shift to see the team at work." : "Nothing needs attention right now."}</p>
          )}
          <ol>
            {shown.map((e) => (
              <li key={e.id} className={e.type === "blocked" ? "blocked" : e.type === "approval" ? "attn" : ""}>
                <span className="who">
                  {time(e.ts)} · {AGENT_NAMES[e.agent] ?? e.agent}
                  {e.deal_id && ` · ${e.deal_id}`}
                  {e.type === "blocked" && " · Blocked"}
                </span>
                <span>{e.text}</span>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}

function heading(waiting: number, running: boolean) {
  if (waiting === 1) return "1 car needs your OK";
  if (waiting > 1) return `${waiting} cars need your OK`;
  return running ? "The team is working" : "The team is paused";
}

function subheading(waiting: number, running: boolean) {
  if (waiting > 0) return "Review each offer below. Approve, decline, or open the details first.";
  if (running) return "Nothing needs you right now. We'll tell you here when a car needs a decision.";
  return "Start today's shift and the agents will look for cars, value them, and talk to sellers.";
}

const count = (deals: Deal[], states: Deal["state"][]) => deals.filter((d) => states.includes(d.state)).length;
