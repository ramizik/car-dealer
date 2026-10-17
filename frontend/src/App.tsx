import { useEffect, useState } from "react";
import { api } from "./api";
import * as fx from "./fixtures";
import BrainView from "./BrainView";
import DealPanel from "./DealPanel";
import EvalView from "./EvalView";
import OnboardingView from "./OnboardingView";
import ShiftView from "./ShiftView";
import type { AgentEvent, Brain, Deal, EvalResult, Health } from "./types";

type Tab = "today" | "memory" | "results" | "setup";

const TABS: { id: Tab; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "memory", label: "Team memory" },
  { id: "results", label: "Results" },
  { id: "setup", label: "Dealer setup" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [health, setHealth] = useState<Health>(fx.health);
  const [deals, setDeals] = useState<Deal[]>(fx.deals);
  const [events, setEvents] = useState<AgentEvent[]>(fx.events);
  const [brain, setBrain] = useState<Brain>(fx.brain);
  const [evalResult, setEvalResult] = useState<EvalResult>(fx.evalResult);
  const [offline, setOffline] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const refresh = async () => {
    const [h, d, e, b, r] = await Promise.all([api.health(), api.deals(), api.events(), api.brain(), api.eval()]);
    // Only replace what the backend actually served; anything missing keeps the current (sample) data.
    setOffline(h.offline || d.offline);
    if (!h.offline) setHealth(h.data);
    if (!d.offline) setDeals(d.data);
    if (!e.offline) setEvents(e.data);
    if (!b.offline) setBrain(b.data);
    if (!r.offline) setEvalResult(r.data);
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const decide = async (id: string, yes: boolean) => {
    const ok = await api.approve(id, yes);
    if (!ok) {
      // Offline: reflect the choice locally so the screen still responds.
      setDeals((ds) =>
        ds.map((d) =>
          d.id === id
            ? yes
              ? { ...d, state: "bought", bought_for: d.offer }
              : { ...d, state: "dropped", drop_reason: "Declined by you" }
            : d,
        ),
      );
    }
    refresh();
  };

  const toggleShift = async () => {
    const running = health.shift_running;
    await (running ? api.stopShift() : api.startShift());
    setHealth((h) => ({ ...h, shift_running: !running }));
  };

  const running = Boolean(health.shift_running);
  const open = deals.find((d) => d.id === openId);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <strong>{health.dealer_name ?? "Your dealership"}</strong>
          <span className={`status ${running ? "on" : ""}`} role="status">
            <i aria-hidden="true" />
            {running ? "Team is working" : "Team is paused"}
          </span>
        </div>

        <nav aria-label="Sections">
          <div className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className="tab"
                aria-current={tab === t.id ? "page" : undefined}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </nav>

        <button className={running ? "" : "primary"} onClick={toggleShift} title={running ? "Stops the agents after their current step" : "Agents start finding and valuing cars"}>
          {running ? "Pause team" : "Start today's shift"}
        </button>
      </header>

      {offline && (
        <div className="banner" role="alert">
          <span>Can't reach the team server, so you're seeing sample data. Nothing you do here is saved yet.</span>
          <button onClick={refresh}>Try again</button>
        </div>
      )}

      <main className="content">
        {tab === "today" && (
          <ShiftView deals={deals} events={events} running={running} onOpen={setOpenId} onDecide={decide} />
        )}
        {tab === "memory" && (
          <section className="stack">
            <div className="page-head">
              <h1>Team memory</h1>
              <p>Everything the agents have learned, shared across the team. Each agent checks it before acting and adds to it afterwards.</p>
            </div>
            <BrainView brain={brain} onSnapshot={(n) => api.loadSnapshot(n).then(refresh)} />
          </section>
        )}
        {tab === "results" && (
          <section className="stack">
            <div className="page-head">
              <h1>Results</h1>
              <p>Does the team's memory make it better? We test the same sellers with and without memory.</p>
            </div>
            <EvalView result={evalResult} onRun={() => api.runEval().then(refresh)} />
          </section>
        )}
        {tab === "setup" && (
          <section className="stack">
            <div className="page-head">
              <h1>Dealer setup</h1>
              <p>Tell the team how you want to buy and sell. Nothing is listed or bid on until you approve.</p>
            </div>
            <OnboardingView />
          </section>
        )}
      </main>

      <footer className="small">
        Nemotron on Crusoe · Search by You.com
        {health.sandboxed && " · Runs in a secure sandbox"}
        {health.demo_mode && " · Demo data"}
        {!health.brain_enabled && " · Team memory off"}
      </footer>

      {open && <DealPanel deal={open} events={events} onClose={() => setOpenId(null)} onDecide={decide} />}
    </div>
  );
}
