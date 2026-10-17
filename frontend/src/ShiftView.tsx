import { useEffect, useState } from "react";
import { api } from "./api";
import ActivityFeed from "./ActivityFeed";
import { agentName, COLUMNS, keyNumber, money, stageLabel, time } from "./format";
import { needsYou, nowFor } from "./status";
import type { AgentEvent, Brain, Deal, DealState, EvalResult, Health } from "./types";

type Props = {
  health: Health | null;
  deals: Deal[];
  events: AgentEvent[];
  brain: Brain | null;
  evalResult: EvalResult | null;
  onStart: () => void;
  onStop: () => void;
  onOpen: (id: string) => void;
  onDecide: (id: string, yes: boolean) => void;
  onSale: (id: string, yes: boolean) => void;
  onInsights: () => void;
};

// The steps every deal walks through. Each one is a real backend state, nothing is staged for the screen.
const STEPS: { label: string; states: DealState[] }[] = [
  { label: "Found", states: ["sourced"] },
  { label: "Valued", states: ["appraised"] },
  { label: "Negotiating", states: ["negotiating"] },
  { label: "Your OK", states: ["awaiting_approval"] },
  { label: "Bought", states: ["bought", "in_transit", "delivered"] },
  { label: "Listed", states: ["listed"] },
  { label: "Sold", states: ["sold"] },
];
const stepOf = (s: DealState) => STEPS.findIndex((x) => x.states.includes(s));

// What the demo does once started. Shown before the button so nobody is surprised.
const PLAN: { title: string; text: string }[] = [
  { title: "Finds cars all day", text: "The scout scans the market for cars that fit your setup and keeps looking as the shift goes on." },
  { title: "Works several deals at once", text: "Up to 4 cars at a time: value it, call the seller, negotiate. New cars arrive while others are in progress." },
  { title: "Asks you only when it must", text: "Clear wins are bought and sold automatically. Borderline buys and sales wait for your OK, and one seller phones in live for you to answer by voice or text." },
  { title: "Sells at the same time", text: "A few cars are already on the lot when the shift opens, so buyers start sending offers right away. Good prices sell on their own; low ones ask you." },
  { title: "Handles everything after the buy", text: "Shipping, the storefront listing and buyer talks run in the background until the car is sold." },
  { title: "Learns as it goes", text: "Every deal writes what worked to the shared brain, so later cars start smarter." },
  { title: "A full shop day in minutes", text: "8 shop hours are compressed into about 5 minutes. You can stop at any time." },
];

const shopClock = (minutes: number) => {
  const t = 8 * 60 + Math.max(0, Math.floor(minutes));
  const h = Math.floor(t / 60);
  const m = t % 60;
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
};
const working = (d: Deal) => d.state === "sourced" || d.state === "appraised" || d.state === "negotiating";

const clock = (secs: number) => {
  const s = Math.max(0, Math.floor(secs));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
};

function useNow() {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export default function ShiftView({ health, deals, events, brain, evalResult, onStart, onStop, onOpen, onDecide, onSale, onInsights }: Props) {
  const now = useNow();
  const shift = health?.shift;
  const running = Boolean(shift?.running);
  const started = shift?.started ?? null;
  const elapsed = started ? (shift?.ended ?? now) - started : 0;
  const inShift = (e: AgentEvent) => !started || e.ts >= started;
  const shiftEvents = events.filter(inShift);

  const writes = shiftEvents.filter((e) => e.type === "write");
  const recalls = shiftEvents.filter((e) => e.type === "recall");

  const inProgress = deals.filter(working);
  const waiting = deals.filter(needsYou);
  const last = events[events.length - 1];

  const decisions = [...shiftEvents].reverse().filter(
    (e) =>
      e.agent === "owner" ||
      e.type === "approval" ||
      (e.type === "recall" && e.text.startsWith("segment=")) ||
      /^(Dropped|Agreed|Bought|Declined|Sold)\b/.test(e.text),
  );
  const findings = [...shiftEvents].reverse().filter(
    (e) => e.type !== "write" && (e.agent === "scout" || e.agent === "appraiser" || e.data?.kind === "resale_quote" || e.type === "blocked"),
  );

  const wrapping = !running && (shift?.active ?? 0) > 0;
  const status = !health ? "Offline" : running ? "Running" : wrapping ? "Wrapping up" : started ? "Finished" : "Ready";

  return (
    <div className="stack">
      {/* Shift control: one button to start. Before it, what will happen; after it, the shop clock and what is in progress. */}
      <section className="mission" aria-labelledby="shift-title">
        <div className="mission-main">
          <span className={`run-state ${running ? "on" : ""}`} role="status">{status}</span>
          <h1 id="shift-title">
            {running
              ? waiting.length
                ? `${waiting.length} ${waiting.length === 1 ? "deal needs" : "deals need"} you`
                : `${inProgress.length} ${inProgress.length === 1 ? "deal" : "deals"} in progress`
              : started
                ? wrapping
                  ? "Wrapping up the day"
                  : waiting.length
                    ? "Shift over, waiting for you"
                    : "Shift complete"
                : "Run a full shop day"}
          </h1>
          <p className="mission-sub">
            {running
              ? waiting.length
                ? `The rest of the team keeps working. ${inProgress.length} more in progress, ${shift?.background ?? 0} shipping, listed or selling.`
                : (shift?.scouting ? "Scanning the market for more cars. " : "") + (last?.text ?? "Starting up")
              : started
                ? `${shift?.n ?? 0} cars worked in ${clock(elapsed)}. ${waiting.length ? `${waiting.length} still need you below.` : "Everything learned is saved for the next shift."}`
                : "Press start and walk away. The team finds cars, calls sellers, negotiates, ships, lists and sells. It pings you only when a decision is yours."}
          </p>
          {!running && !started && (
            <ol className="plan" aria-label="What happens after you start">
              {PLAN.map((p, i) => (
                <li key={p.title}>
                  <span className="plan-n mono">{i + 1}</span>
                  <span><strong>{p.title}</strong><span className="small muted">{p.text}</span></span>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div className="mission-side">
          <dl className="clock-grid">
            <div><dt>Shop clock</dt><dd className="mono">{started ? shopClock(shift?.sim_minutes ?? 0) : "8:00 AM"}</dd></div>
            <div><dt>Cars worked</dt><dd className="mono">{shift?.n ?? 0}</dd></div>
          </dl>
          <div className="progress big" role="img" aria-label="Shift progress">
            <div style={{ width: `${Math.round((shift?.progress ?? 0) * 100)}%` }} className={running ? "live" : ""} />
          </div>
          {running ? (
            <button onClick={onStop}>Stop demo</button>
          ) : (
            <button className="primary big" onClick={onStart} disabled={!health || wrapping}>{started ? "Start again" : "Start Demo"}</button>
          )}
        </div>
      </section>

      {/* Needs you: only things a person must do, each with its own button. Everything else is on the board below. */}
      <section className={`needs-you ${waiting.length ? "" : "calm"}`} aria-labelledby="needs-you-title">
        <h2 id="needs-you-title">Needs you ({waiting.length})</h2>
        {waiting.length === 0 ? (
          <p className="small muted">Nothing to decide right now. The team is working; clear wins are handled automatically.</p>
        ) : (
          <ul>
            {waiting.map((d) => {
              const n = nowFor(d);
              const name = d.car.split(" · ")[0];
              const kind = n.action === "seller" ? "Live call" : n.action === "sale" ? "Sell offer" : "Buy offer";
              return (
                <li key={d.id} className="need">
                  <span className={`kind k-${n.action}`}>{kind}</span>
                  <span className="need-main">
                    <strong>{name}</strong> <span className="muted small">{d.id}</span>
                    <span className="small">
                      {n.action === "sale"
                        ? `A buyer will pay ${money(d.sale_offer)} (listed ${money(d.list_price)}, paid ${money(d.bought_for)}).`
                        : n.action === "approve"
                          ? `Seller agreed ${money(d.offer)} (asked ${money(d.asking)}, your max ${money(d.max_buy)}).`
                          : "A seller is on the line. Answer by voice or text."}
                    </span>
                  </span>
                  <span className="actions">
                    {n.action === "approve" && (<><button onClick={() => onDecide(d.id, false)}>Decline</button><button className="primary" onClick={() => onDecide(d.id, true)}>Buy</button></>)}
                    {n.action === "sale" && (<><button onClick={() => onSale(d.id, false)}>Keep talking</button><button className="primary" onClick={() => onSale(d.id, true)}>Sell</button></>)}
                    {n.action === "seller" && <button className="primary" onClick={() => onOpen(d.id)}>Take the call</button>}
                    {n.action !== "seller" && <button className="quiet" onClick={() => onOpen(d.id)}>Details</button>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Pipeline: how many deals sit at each step, then every deal on its own track. */}
      <section className="panel" aria-labelledby="pipeline">
        <div className="panel-head">
          <h2 id="pipeline">Deal board</h2>
          <span className="muted small">{deals.length} deals · {deals.filter((d) => d.state === "dropped").length} stopped · <a href={api.storefrontUrl} target="_blank" rel="noreferrer">Storefront</a></span>
        </div>
        <ol className="stepper">
          {STEPS.map((s, i) => {
            const n = deals.filter((d) => s.states.includes(d.state)).length;
            const active = running && inProgress.some((d) => stepOf(d.state) === i);
            return (
              <li key={s.label} className={`${n ? "has" : ""} ${active ? "active" : ""}`}>
                <span className="step-n mono">{n}</span>
                <span className="step-l">{s.label}</span>
              </li>
            );
          })}
        </ol>
        {deals.length === 0 ? (
          <p className="empty">No deals yet. Press Start Demo and each car appears here as it moves through the steps.</p>
        ) : (
          <div className="lanes">
            {[...COLUMNS, { title: "Stopped", hint: "Walked away, scams, over budget", states: ["dropped" as DealState] }].map((col) => {
              const rows = deals.filter((d) => col.states.includes(d.state));
              return (
                <section key={col.title} className="lane" aria-label={col.title}>
                  <header><h3>{col.title}</h3><span className="lane-n mono">{rows.length}</span></header>
                  <p className="small muted">{col.hint}</p>
                  <ul>
                    {rows.slice(0, 8).map((d) => {
                      const mine = events.filter((e) => e.deal_id === d.id);
                      const said = [...mine].reverse().find((e) => !["recall", "write", "skill"].includes(e.type));
                      const asks = needsYou(d);
                      return (
                        <li key={d.id}>
                          <button className={`card ${asks ? "asks" : ""} ${running && working(d) ? "busy" : ""}`} onClick={() => onOpen(d.id)}>
                            <span className="card-top">
                              <strong>{d.car.split(" · ")[0]}</strong>
                              <span className="muted small mono">{d.id}</span>
                            </span>
                            <span className="small card-step">{asks ? "Needs you" : d.state === "dropped" ? `Stopped: ${d.drop_reason}` : stageLabel(d.state)}</span>
                            <span className="small muted">{d.state === "dropped" ? "" : keyNumber(d)}</span>
                            {said && d.state !== "dropped" && <span className="small muted card-said">{said.text}</span>}
                          </button>
                        </li>
                      );
                    })}
                    {rows.length === 0 && <li className="small muted lane-empty">None</li>}
                  </ul>
                </section>
              );
            })}
          </div>
        )}
      </section>

      <div className="two-col">
        {/* Decisions: what needs the owner, then what the team decided on its own. */}
        <section className="panel" aria-labelledby="decisions">
          <div className="panel-head">
            <h2 id="decisions">Team decisions</h2>
            <span className="muted small">what it chose on its own</span>
          </div>
          <Log items={decisions} empty="Tactic picks, buys, drops and your answers show up here." onOpen={onOpen} render={decisionText} />
        </section>

        {/* Findings: what scouting, valuing and the sales desk found out. */}
        <section className="panel" aria-labelledby="findings">
          <div className="panel-head">
            <h2 id="findings">Findings</h2>
            <span className="muted small">market, value, resale, red flags</span>
          </div>
          <Log items={findings} empty="Market scans, valuations and resale quotes show up here." onOpen={onOpen} render={(e) => e.text} />
        </section>
      </div>

      <div className="two-col">
        {/* Shared brain: read before work, write after. */}
        <section className="panel" aria-labelledby="memories">
          <div className="panel-head">
            <h2 id="memories">Recent memories</h2>
            <span className="muted small mono">{brain?.stats.events ?? 0} total · {Math.round((brain?.stats.bytes ?? 0) / 1024)} KB</span>
          </div>
          <div className="loop" aria-label="Memory loop">
            <span><b className="mono">{recalls.length}</b> read before work</span>
            <span><b className="mono">{writes.length}</b> written after</span>
            <span><b className="mono">{brain?.stats.conflicts ?? 0}</b> conflicts</span>
          </div>
          {writes.length === 0 ? (
            <p className="empty">Nothing learned this shift yet. Each valuation, sale and negotiation writes here.</p>
          ) : (
            <ol className="memlist">
              {[...writes].reverse().slice(0, 12).map((e) => (
                <li key={e.id}>
                  <span className={`scope s-${String(e.data.scope)}`}>{String(e.data.scope)}</span>
                  <span className="mem-text">
                    <strong>{String(e.data.key)}</strong>
                    <span className="muted small">{e.text.split(": ").slice(1).join(": ")}</span>
                  </span>
                  <span className="muted small mono">{agentName(e.agent)} {time(e.ts)}</span>
                </li>
              ))}
            </ol>
          )}
          <Learning result={evalResult} onMore={onInsights} />
        </section>

        <ActivityFeed events={events} onOpen={onOpen} limit={14} />
      </div>
    </div>
  );
}

const decisionText = (e: AgentEvent) =>
  e.type === "recall" && e.text.startsWith("segment=")
    ? `Chose tactic "${e.text.split("tactic=")[1]?.replace(/_/g, " ")}" for a ${e.text.split(",")[0].slice(8).replace(/_/g, " ")} seller`
    : e.text;

function Log({ items, empty, onOpen, render }: { items: AgentEvent[]; empty: string; onOpen: (id: string) => void; render: (e: AgentEvent) => string }) {
  if (items.length === 0) return <p className="empty">{empty}</p>;
  return (
    <ol className="log">
      {items.slice(0, 10).map((e) => (
        <li key={e.id} className={e.type === "blocked" ? "blocked" : e.type === "approval" ? "attn" : ""}>
          <span className="who mono">{time(e.ts)} {agentName(e.agent)}</span>
          {e.deal_id ? <button className="feed-link" onClick={() => onOpen(e.deal_id!)}>{render(e)}</button> : <span>{render(e)}</span>}
        </li>
      ))}
    </ol>
  );
}

// Last measured brain OFF vs ON run (backend/eval.py). Shows whatever the numbers are, good or bad.
function Learning({ result, onMore }: { result: EvalResult | null; onMore: () => void }) {
  if (!result || result.missing || !result.on || !result.off) {
    return <p className="empty">No learning test yet. Run <code>python eval.py</code> in backend to measure brain OFF vs ON.</p>;
  }
  const rows: [string, number, number, string][] = [
    ["Close rate", result.off.close_rate * 100, result.on.close_rate * 100, "%"],
    ["Saved off asking", result.off.mean_saved_pct, result.on.mean_saved_pct, "%"],
    ["Rounds to close", result.off.mean_rounds, result.on.mean_rounds, ""],
  ];
  return (
    <div className="learn">
      <div className="row-between">
        <strong>Measured: brain off vs on</strong>
        <button className="quiet" onClick={onMore}>Details</button>
      </div>
      <p className="muted small">{result.heldout_n} unseen sellers, after {result.train_n} training deals.</p>
      <table className="mini">
        <thead><tr><th></th><th className="num">Off</th><th className="num">On</th></tr></thead>
        <tbody>
          {rows.map(([n, off, on, u]) => (
            <tr key={n}><td>{n}</td><td className="num mono">{off.toFixed(1)}{u}</td><td className="num mono">{on.toFixed(1)}{u}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
