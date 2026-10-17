import ActivityFeed from "./ActivityFeed";
import { greeting, money, profit, stageLabel } from "./format";
import type { AgentEvent, Deal } from "./types";

type Props = {
  dealer: string;
  deals: Deal[];
  events: AgentEvent[];
  running: boolean;
  onToggle: () => void;
  onOpen: (id: string) => void;
  onDecide: (id: string, yes: boolean) => void;
  onGo: (section: "buying" | "inventory" | "selling" | "setup") => void;
};

const BOUGHT = ["bought", "in_transit", "delivered", "listed", "sold"];

// Home answers three questions in order: what needs me, how is the business doing, what is happening.
export default function HomeView({ dealer, deals, events, running, onToggle, onOpen, onDecide, onGo }: Props) {
  const approvals = deals.filter((d) => d.state === "awaiting_approval");
  const flagged = deals.filter((d) => d.state === "dropped" && /block|scam|link|escrow/i.test(d.drop_reason ?? ""));
  const needs = approvals.length + flagged.length;
  const sold = deals.filter((d) => d.state === "sold");
  const earned = sold.reduce((s, d) => s + (profit(d) ?? 0), 0);
  const buying = deals.filter((d) => ["sourced", "appraised", "negotiating"].includes(d.state));

  return (
    <div className="stack">
      <header className="page-head">
        <p className="eyebrow">{greeting()}, {dealer}</p>
        <h1>{needs ? `${needs} ${needs === 1 ? "thing needs" : "things need"} you` : "You're all caught up"}</h1>
        <p>{needs ? "Decide on these and we keep going." : running ? "We're finding and buying cars for you. Anything that needs you shows up here." : "Buying is paused."}</p>
      </header>

      {!running && (
        <div className="callout">
          <div>
            <strong>Start buying</strong>
            <p>We find cars that fit your lot, value them and talk to sellers. Nothing is bought without your OK.</p>
          </div>
          <button className="primary" onClick={onToggle}>Start buying</button>
        </div>
      )}

      {needs > 0 && (
        <section aria-labelledby="inbox" className="stack-sm">
          <h2 id="inbox">Needs you</h2>
          {approvals.map((d) => (
            <article key={d.id} className="inbox-item attn">
              <div className="inbox-body">
                <span className="tag attn">Approve a buy</span>
                <h3>{d.car.split(" · ")[0]}</h3>
                <p>
                  Offer <strong>{money(d.offer)}</strong> · asking {money(d.asking)} · your max {money(d.max_buy)}
                  {d.valuation && <> · worth about {money(d.valuation.mid)}</>}
                </p>
              </div>
              <div className="actions">
                <button className="quiet" onClick={() => onOpen(d.id)}>Details</button>
                <button onClick={() => onDecide(d.id, false)}>Decline</button>
                <button className="primary" onClick={() => onDecide(d.id, true)}>Approve</button>
              </div>
            </article>
          ))}
          {flagged.map((d) => (
            <article key={d.id} className="inbox-item danger">
              <div className="inbox-body">
                <span className="tag danger">Stopped for safety</span>
                <h3>{d.car.split(" · ")[0]}</h3>
                <p>{d.drop_reason}</p>
              </div>
              <div className="actions">
                <button onClick={() => onOpen(d.id)}>Review</button>
              </div>
            </article>
          ))}
        </section>
      )}

      <section className="kpis" aria-label="Business at a glance">
        <button className="kpi" onClick={() => onGo("buying")}>
          <span className="value">{buying.length + approvals.length}</span>
          <span className="label">Cars being bought</span>
        </button>
        <button className="kpi" onClick={() => onGo("inventory")}>
          <span className="value">{deals.filter((d) => BOUGHT.slice(0, 3).includes(d.state)).length}</span>
          <span className="label">Bought, not listed</span>
        </button>
        <button className="kpi" onClick={() => onGo("selling")}>
          <span className="value">{deals.filter((d) => d.state === "listed").length}</span>
          <span className="label">For sale</span>
        </button>
        <button className="kpi" onClick={() => onGo("selling")}>
          <span className="value">{money(earned)}</span>
          <span className="label">Profit from {sold.length} sold</span>
        </button>
      </section>

      <div className="two-col">
        <section className="panel" aria-labelledby="progress">
          <div className="panel-head">
            <h2 id="progress">In progress</h2>
            <button className="quiet" onClick={() => onGo("buying")}>See all</button>
          </div>
          {buying.length === 0 && <p className="empty">No cars in progress.</p>}
          <ul className="mini-list">
            {buying.slice(0, 4).map((d) => (
              <li key={d.id}>
                <button onClick={() => onOpen(d.id)}>
                  <span className="car">{d.car}</span>
                  <span className="row-between">
                    <span className="pill">{stageLabel(d.state)}</span>
                    <span className="muted small">{d.offer ? `Offer ${money(d.offer)}` : `Asks ${money(d.asking)}`}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="setup-nudge">
            <span className="muted small">Want different cars?</span>
            <button className="quiet" onClick={() => onGo("setup")}>Update your setup</button>
          </div>
        </section>

        <ActivityFeed events={events} onOpen={onOpen} limit={12} />
      </div>
    </div>
  );
}
