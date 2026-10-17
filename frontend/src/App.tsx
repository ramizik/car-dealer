import { useEffect, useState } from "react";
import { api } from "./api";
import * as fx from "./fixtures";
import BrainView from "./BrainView";
import DealPanel from "./DealPanel";
import EvalView from "./EvalView";
import OnboardingView from "./OnboardingView";
import ShiftView from "./ShiftView";
import type { AgentEvent, Brain, Deal, EvalResult, Health } from "./types";

type Tab = "shift" | "brain" | "eval" | "dealer";

const TABS: { id: Tab; label: string }[] = [
  { id: "shift", label: "Shift" },
  { id: "brain", label: "Brain" },
  { id: "eval", label: "Results" },
  { id: "dealer", label: "Dealer setup" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("shift");
  const [health, setHealth] = useState<Health>(fx.health);
  const [deals, setDeals] = useState<Deal[]>(fx.deals);
  const [events, setEvents] = useState<AgentEvent[]>(fx.events);
  const [brain, setBrain] = useState<Brain>(fx.brain);
  const [evalResult, setEvalResult] = useState<EvalResult>(fx.evalResult);
  const [offline, setOffline] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const refresh = async () => {
    const [h, d, e, b, r] = await Promise.all([api.health(), api.deals(), api.events(), api.brain(), api.eval()]);
    // Only replace what the backend actually served; anything missing keeps current (sample) data.
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

  const open = deals.find((d) => d.id === openId);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <strong>{health.dealer_name ?? "Your dealership"}</strong>
          <span className="muted">
            {health.shift_running ? "● Agents working" : "○ Agents idle"}
          </span>
        </div>
        <nav>
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? "tab active" : "tab"} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="row">
          {offline && <span className="badge warn" title="Backend not reachable. Showing sample data.">Offline · sample data</span>}
          {health.demo_mode && <span className="badge">Demo</span>}
          {health.sandboxed && <span className="badge" title="Agents run inside an NVIDIA OpenShell sandbox">Sandboxed</span>}
          {!health.brain_enabled && <span className="badge warn">Brain off</span>}
          <button className="primary" onClick={toggleShift}>
            {health.shift_running ? "Stop shift" : "Start shift"}
          </button>
        </div>
      </header>

      <div className="content">
        {tab === "shift" && <ShiftView deals={deals} events={events} onOpen={setOpenId} onDecide={decide} />}
        {tab === "brain" && <BrainView brain={brain} onSnapshot={(n) => api.loadSnapshot(n).then(refresh)} />}
        {tab === "eval" && <EvalView result={evalResult} onRun={() => api.runEval().then(refresh)} />}
        {tab === "dealer" && <OnboardingView />}
      </div>

      <footer className="muted small">Nemotron on Crusoe · Search by You.com</footer>

      {open && <DealPanel deal={open} events={events} onClose={() => setOpenId(null)} onDecide={decide} />}
    </div>
  );
}
