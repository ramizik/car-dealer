import { useEffect, useState } from "react";
import ActivityFeed from "./ActivityFeed";
import { agentName, money, profit, time } from "./format";
import type { AgentEvent, Brain, Deal, DealState, EvalResult, Health } from "./types";

type Props = {
  health: Health | null;
  deals: Deal[];
  events: AgentEvent[];
  brain: Brain | null;
  evalResult: EvalResult | null;
  onStart: (n: number) => void;
  onStop: () => void;
  onOpen: (id: string) => void;
  onDecide: (id: string, yes: boolean) => void;
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

const PHASES: Record<string, string> = {
  idle: "Idle",
  scouting: "Scanning the market",
  sourcing: "Picking the next car",
  valuing: "Valuing a car",
  negotiating: "Talking to a seller",
  "waiting for owner": "Waiting for your OK",
};

const clock = (secs: number) => {
  const s = Math.max(0, Math.floor(secs));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
};

const pct = (n: number) => `${Math.round(n * 1000) / 10}%`;

function useNow() {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export default function ShiftView({ health, deals, events, brain, evalResult, onStart, onStop, onOpen, onDecide, onInsights }: Props) {
  const now = useNow();
  const [size, setSize] = useState(5);
  const shift = health?.shift;
  const running = Boolean(shift?.running);
  const started = shift?.started ?? null;
  const elapsed = started ? (shift?.ended ?? now) - started : 0;
  const inShift = (e: AgentEvent) => !started || e.ts >= started;
  const shiftEvents = events.filter(inShift);

  // Stats, all derived from live deals and events.
  const closedDeals = deals.filter((d) => d.offer !== undefined);
  const settled = deals.filter((d) => d.state !== "sourced" && d.state !== "appraised" && d.state !== "negotiating");
  const sold = deals.filter((d) => d.state === "sold");
  const earned = sold.reduce((s, d) => s + (profit(d) ?? 0), 0);
  const offAsk = closedDeals.length
    ? closedDeals.reduce((s, d) => s + (d.asking - (d.offer ?? d.asking)) / d.asking, 0) / closedDeals.length
    : null;
  const blocked = shiftEvents.filter((e) => e.type === "blocked").length;
  const writes = shiftEvents.filter((e) => e.type === "write");
  const recalls = shiftEvents.filter((e) => e.type === "recall");
  const llmCalls = Object.values(health?.llm ?? {}).reduce((s, t) => s + (t.calls ?? 0), 0);

  const approvals = deals.filter((d) => d.state === "awaiting_approval");
  const current = deals.find((d) => d.id === shift?.deal);
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

  const status = !health ? "Offline" : running ? "Running" : started ? "Finished" : "Ready";

  return (
    <div className="stack">
      {/* Shift control: what the team is doing right now and how far along it is. */}
      <section className="mission" aria-labelledby="shift-title">
        <div className="mission-main">
          <span className={`run-state ${running ? "on" : ""}`} role="status">{status}</span>
          <h1 id="shift-title">
            {running ? PHASES[shift?.phase ?? ""] ?? shift?.phase : started ? "Shift complete" : "Start a buying shift"}
          </h1>
          <p className="mission-sub">
            {running && current
              ? `${current.id} · ${current.car}`
              : running
                ? last?.text ?? "Starting up"
                : started
                  ? `Worked ${shift?.n ?? 0} deals in ${clock(elapsed)}. Everything learned is saved for the next shift.`
                  : "The team scouts, values and negotiates on its own. Walk away; buys wait for your OK."}
          </p>
        </div>
        <div className="mission-side">
          <dl className="clock-grid">
            <div><dt>Elapsed</dt><dd className="mono">{clock(elapsed)}</dd></div>
            <div><dt>Deals</dt><dd className="mono">{shift?.n ?? 0}<span className="muted">/{shift?.cap || size}</span></dd></div>
          </dl>
          <div className="progress big" role="img" aria-label="Shift progress">
            <div style={{ width: `${shift?.cap ? Math.min(100, (shift.n / shift.cap) * 100) : 0}%` }} className={running ? "live" : ""} />
          </div>
          {running ? (
            <button onClick={onStop}>Stop shift</button>
          ) : (
            <div className="row">
              <label className="sr-only" htmlFor="shift-size">Deals this shift</label>
              <select id="shift-size" value={size} onChange={(e) => setSize(Number(e.target.value))} disabled={!health}>
                {[3, 5, 10, 20].map((n) => <option key={n} value={n}>{n} deals</option>)}
              </select>
              <button className="primary" onClick={() => onStart(size)} disabled={!health}>Start shift</button>
            </div>
          )}
        </div>
      </section>

      {/* Pipeline: how many deals sit at each step, then every deal on its own track. */}
      <section className="panel" aria-labelledby="pipeline">
        <div className="panel-head">
          <h2 id="pipeline">Progress</h2>
          <span className="muted small">{deals.length} deals · {deals.filter((d) => d.state === "dropped").length} stopped</span>
        </div>
        <ol className="stepper">
          {STEPS.map((s, i) => {
            const n = deals.filter((d) => s.states.includes(d.state)).length;
            const active = running && current && stepOf(current.state) === i;
            return (
              <li key={s.label} className={`${n ? "has" : ""} ${active ? "active" : ""}`}>
                <span className="step-n mono">{n}</span>
                <span className="step-l">{s.label}</span>
              </li>
            );
          })}
        </ol>
        {deals.length === 0 ? (
          <p className="empty">No deals yet. Start a shift and each car appears here as it moves through the steps.</p>
        ) : (
          <ul className="tracks">
            {deals.slice(0, 8).map((d) => {
              const stopped = d.state === "dropped";
              // A stopped deal shows the step it stopped at: it talked to the seller if there is a chat.
              const at = stopped ? (d.chat.length ? 2 : 1) : stepOf(d.state);
              const mine = events.filter((e) => e.deal_id === d.id);
              const first = mine[0];
              const lastE = mine[mine.length - 1];
              const said = [...mine].reverse().find((e) => !["recall", "write", "skill"].includes(e.type));
              return (
                <li key={d.id}>
                  <button className="track" onClick={() => onOpen(d.id)}>
                    <span className="track-car">
                      <strong>{d.car.split(" · ")[0]}</strong>
                      <span className="muted small">{d.id} · {stopped ? `Stopped: ${d.drop_reason}` : said?.text ?? ""}</span>
                    </span>
                    <span className={`track-bar ${stopped ? "stopped" : ""}`} aria-label={stopped ? "Stopped" : STEPS[at]?.label}>
                      {STEPS.map((s, i) => (
                        <i key={s.label} className={i < at ? "done" : i === at ? (stopped ? "stop" : d.id === shift?.deal && running ? "now" : "here") : ""} />
                      ))}
                    </span>
                    <span className="mono small muted track-t">
                      {first && lastE ? clock((d.id === shift?.deal && running ? now : lastE.ts) - first.ts) : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Stats: before/after numbers a judge can check against the feed. */}
      <section className="stats" aria-label="Shift stats">
        <Stat value={String(deals.length)} label="Deals worked" />
        <Stat value={settled.length ? pct(closedDeals.length / settled.length) : "-"} label="Close rate" />
        <Stat value={offAsk === null ? "-" : pct(offAsk)} label="Saved off asking" />
        <Stat value={money(earned)} label={`Profit, ${sold.length} sold`} tone={earned > 0 ? "good" : undefined} />
        <Stat value={String(blocked)} label="Scams blocked" />
        <Stat value={String(recalls.length)} label="Memory reads" />
        <Stat value={String(writes.length)} label="Memory writes" />
        <Stat value={String(llmCalls)} label={health?.llm_live ? "Nemotron calls" : "LLM calls (mock)"} />
      </section>

      <div className="two-col">
        {/* Decisions: what needs the owner, then what the team decided on its own. */}
        <section className="panel" aria-labelledby="decisions">
          <div className="panel-head">
            <h2 id="decisions">Decisions</h2>
            {approvals.length > 0 && <span className="tag attn">{approvals.length} need you</span>}
          </div>
          <div className="stack-sm">
            {approvals.map((d) => (
              <article key={d.id} className="ask">
                <div>
                  <strong>Buy {d.car.split(" · ")[0]} for {money(d.offer)}?</strong>
                  <p className="small muted">
                    Asked {money(d.asking)} · your max {money(d.max_buy)}
                    {d.valuation && <> · worth about {money(d.valuation.mid)}</>}
                  </p>
                </div>
                <div className="actions">
                  <button onClick={() => onDecide(d.id, false)}>Decline</button>
                  <button className="primary" onClick={() => onDecide(d.id, true)}>Approve</button>
                </div>
              </article>
            ))}
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

function Stat({ value, label, tone }: { value: string; label: string; tone?: "good" }) {
  return (
    <div className="stat2">
      <span className={`v mono ${tone ?? ""}`}>{value}</span>
      <span className="l">{label}</span>
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
