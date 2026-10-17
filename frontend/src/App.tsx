import { useEffect, useState } from "react";
import { api } from "./api";
import BrainView from "./BrainView";
import DealPanel from "./DealPanel";
import DealsList, { type Column, type Filter } from "./DealsList";
import EvalView from "./EvalView";
import ShiftView from "./ShiftView";
import MoneyView from "./MoneyView";
import OnboardingView from "./OnboardingView";
import { money, profit, stageLabel } from "./format";
import type { AgentEvent, Brain, Deal, EvalResult, Health } from "./types";

type Section = "home" | "buying" | "inventory" | "selling" | "team" | "setup";

const NAV: { id: Section; label: string; icon: string; mobile: boolean }[] = [
  { id: "home", label: "Shift", icon: "◉", mobile: true },
  { id: "buying", label: "Buying", icon: "⇣", mobile: true },
  { id: "inventory", label: "Inventory", icon: "▦", mobile: true },
  { id: "selling", label: "Selling", icon: "⇡", mobile: true },
  { id: "team", label: "Insights", icon: "◎", mobile: true },
  { id: "setup", label: "Setup", icon: "⚙", mobile: false },
];

export default function App() {
  const [section, setSection] = useState<Section>("home");
  const [teamTab, setTeamTab] = useState<"money" | "memory" | "results">("memory");
  // Everything on screen comes from the backend. Nothing is shown until it answers.
  const [health, setHealth] = useState<Health | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [brain, setBrain] = useState<Brain | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [offline, setOffline] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const refresh = async () => {
    const [h, d, e, b, r] = await Promise.all([api.health(), api.deals(), api.events(), api.brain(), api.eval()]);
    setOffline(h === null);
    setHealth(h);
    if (d) setDeals(d);
    if (e) setEvents(e);
    if (b) setBrain(b);
    if (r) setEvalResult(r);
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const decide = async (id: string, yes: boolean) => {
    // The dealer's answer is saved so the team acts on it next time.
    await api.approve(id, yes, deals.find((d) => d.id === id)?.car ?? "");
    refresh();
  };

  const startShift = async (n: number) => {
    await api.startShift(n);
    refresh();
  };
  const stopShift = async () => {
    await api.stopShift();
    refresh();
  };
  const toggleShift = () => (health?.shift_running ? stopShift() : startShift(5));

  const go = (s: Section) => {
    setSection(s);
    window.scrollTo({ top: 0 });
  };

  const running = Boolean(health?.shift_running);
  const open = deals.find((d) => d.id === openId);
  const needs = deals.filter((d) => d.state === "awaiting_approval").length;
  const badge: Partial<Record<Section, number>> = { home: needs, buying: needs };

  // Latest sales-desk answer per deal: resale price, days to sell, profit.
  const quote = (d: Deal) => {
    const e = [...events].reverse().find((x) => x.deal_id === d.id && x.data?.kind === "resale_quote");
    const q = e?.data as { resale_price?: number; days_to_sell?: number; profit?: number } | undefined;
    if (!q?.resale_price) return <span className="muted">—</span>;
    return (
      <span>
        {money(q.resale_price)} · {Math.round(q.days_to_sell ?? 0)}d
        <span className={`small ${(q.profit ?? 0) >= 0 ? "good" : "bad"}`}> {(q.profit ?? 0) >= 0 ? "+" : ""}{money(q.profit)}</span>
      </span>
    );
  };

  const status = (d: Deal) => (
    <span className={`pill ${d.state === "awaiting_approval" ? "attn" : d.state === "sold" ? "ok" : d.state === "dropped" ? "stop" : ""}`}>
      {stageLabel(d.state)}
    </span>
  );

  const buyingCols: Column[] = [
    { label: "Status", render: status },
    { label: "Asking", render: (d) => money(d.asking), numeric: true },
    { label: "Our offer", render: (d) => money(d.offer), numeric: true },
    { label: "Your max", render: (d) => money(d.max_buy), numeric: true },
    { label: "Resale estimate", render: quote },
  ];
  const buyingFilters: Filter[] = [
    { id: "all", label: "All", states: ["sourced", "appraised", "negotiating", "awaiting_approval"] },
    { id: "you", label: "Needs you", states: ["awaiting_approval"] },
    { id: "talk", label: "Negotiating", states: ["negotiating"] },
    { id: "find", label: "Found and valued", states: ["sourced", "appraised"] },
    { id: "stop", label: "Stopped", states: ["dropped"] },
  ];

  const inventoryCols: Column[] = [
    { label: "Status", render: status },
    { label: "Paid", render: (d) => money(d.bought_for), numeric: true },
    { label: "Worth about", render: (d) => money(d.valuation?.mid), numeric: true },
  ];
  const inventoryFilters: Filter[] = [
    { id: "all", label: "All", states: ["bought", "in_transit", "delivered"] },
    { id: "way", label: "On the way", states: ["bought", "in_transit"] },
    { id: "lot", label: "On the lot", states: ["delivered"] },
  ];

  const sellingCols: Column[] = [
    { label: "Status", render: status },
    { label: "Paid", render: (d) => money(d.bought_for), numeric: true },
    { label: "Listed at", render: (d) => money(d.list_price), numeric: true },
    { label: "Sold for", render: (d) => money(d.sold_for), numeric: true },
    {
      label: "Profit",
      numeric: true,
      render: (d) => {
        const p = profit(d);
        return p === undefined ? <span className="muted">—</span> : <span className={p >= 0 ? "good" : "bad"}>{p >= 0 ? "+" : ""}{money(p)}</span>;
      },
    },
  ];
  const sellingFilters: Filter[] = [
    { id: "all", label: "All", states: ["listed", "sold"] },
    { id: "sale", label: "For sale", states: ["listed"] },
    { id: "sold", label: "Sold", states: ["sold"] },
  ];

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main">
        <div className="brand">
          <span className="logo" aria-hidden="true">D</span>
          <div>
            <strong>{health?.dealer_name ?? "Your dealership"}</strong>
            <span className="muted small">{!health ? "Backend offline" : health.llm_live ? "Live on Nemotron" : "LLM mock mode"}</span>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <button key={n.id} className="nav-item" aria-current={section === n.id ? "page" : undefined} onClick={() => go(n.id)}>
              <span className="nav-icon" aria-hidden="true">{n.icon}</span>
              {n.label}
              {badge[n.id] ? <span className="nav-badge" aria-label={`${badge[n.id]} need you`}>{badge[n.id]}</span> : null}
            </button>
          ))}
        </nav>
        <div className="team-card">
          <span className={`status ${running ? "on" : ""}`} role="status">
            <i aria-hidden="true" />
            {running ? `Shift running · ${health?.shift?.n ?? 0}/${health?.shift?.cap ?? 0}` : "No shift running"}
          </span>
          <button className={running ? "" : "primary"} onClick={toggleShift} disabled={!health}>
            {running ? "Stop shift" : "Start shift"}
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="mobile-top">
          <strong>{health?.dealer_name ?? "Your dealership"}</strong>
          <div className="row">
            <span className={`status ${running ? "on" : ""}`}><i aria-hidden="true" />{running ? "Shift on" : "Idle"}</span>
            <button className="quiet" onClick={() => go("setup")}>Setup</button>
          </div>
        </header>

        {offline && (
          <div className="banner" role="alert">
            <span>Can't reach the backend. Nothing below is live until it answers.</span>
            <button onClick={refresh}>Try again</button>
          </div>
        )}

        <main className="content">
          {section === "home" && (
            <ShiftView health={health} deals={deals} events={events} brain={brain} evalResult={evalResult}
              onStart={startShift} onStop={stopShift} onOpen={setOpenId} onDecide={decide}
              onInsights={() => { setTeamTab("results"); go("team"); }} />
          )}
          {section === "buying" && (
            <DealsList title="Buying" intro="Cars we found, valued and are negotiating. We check resale price and profit before any buy."
              deals={deals} filters={buyingFilters} columns={buyingCols} empty="Nothing here yet. Start buying to find cars." onOpen={setOpenId} />
          )}
          {section === "inventory" && (
            <DealsList title="Inventory" intro="Cars you've bought, on the way or on the lot."
              deals={deals} filters={inventoryFilters} columns={inventoryCols} empty="No cars here yet." onOpen={setOpenId} />
          )}
          {section === "selling" && (
            <DealsList title="Selling" intro="Your listings and what sold, with profit on each car."
              deals={deals} filters={sellingFilters} columns={sellingCols} empty="No listings yet." onOpen={setOpenId} />
          )}
          {section === "team" && (
            <div className="stack">
              <header className="page-head">
                <h1>Insights</h1>
                <p>The shared brain every agent reads before work and writes after, and what it measurably changes.</p>
              </header>
              <div className="seg seg-lg" role="group" aria-label="Insights view">
                <button aria-pressed={teamTab === "memory"} onClick={() => setTeamTab("memory")}>Shared brain</button>
                <button aria-pressed={teamTab === "results"} onClick={() => setTeamTab("results")}>Brain off vs on</button>
                <button aria-pressed={teamTab === "money"} onClick={() => setTeamTab("money")}>Money</button>
              </div>
              {teamTab === "money" ? (
                <MoneyView deals={deals} />
              ) : teamTab === "memory" ? (
                <BrainView brain={brain} onSnapshot={(n) => api.loadSnapshot(n).then(refresh)} />
              ) : (
                <EvalView result={evalResult} />
              )}
            </div>
          )}
          {section === "setup" && (
            <div className="stack">
              <header className="page-head">
                <h1>Setup</h1>
                <p>Tell us what you buy and sell. Takes about two minutes. Nothing is listed or bid on without your OK.</p>
              </header>
              <OnboardingView />
            </div>
          )}
        </main>

      </div>

      <nav className="bottom-nav" aria-label="Main">
        {NAV.filter((n) => n.mobile).map((n) => (
          <button key={n.id} aria-current={section === n.id ? "page" : undefined} onClick={() => go(n.id)}>
            <span className="nav-icon" aria-hidden="true">{n.icon}</span>
            <span>{n.label}</span>
            {badge[n.id] ? <span className="nav-badge">{badge[n.id]}</span> : null}
          </button>
        ))}
      </nav>

      {open && <DealPanel deal={open} events={events} onClose={() => setOpenId(null)} onDecide={decide} />}
    </div>
  );
}
