// Offline fallback so the UI never renders blank (roadmap 2.C1).
import type { AgentEvent, Brain, Deal, EvalResult, Health } from "./types";

export const health: Health = {
  ok: true,
  demo_mode: true,
  brain_enabled: true,
  sandboxed: true,
  shift_running: true,
  dealer_name: "Joe's Auto",
};

export const deals: Deal[] = [
  {
    id: "D-104",
    car: "2018 Toyota Tacoma SR5 · 61k mi",
    location: "Fresno, CA",
    state: "awaiting_approval",
    asking: 26500,
    offer: 23900,
    max_buy: 24500,
    valuation: {
      low: 25800,
      mid: 27400,
      high: 28900,
      citations: [
        { title: "KBB: 2018 Tacoma SR5 private party value", url: "https://www.kbb.com/toyota/tacoma/2018/" },
        { title: "Edmunds: Tacoma SR5 used prices near Fresno", url: "https://www.edmunds.com/toyota/tacoma/2018/" },
      ],
    },
    chat: [
      {
        from: "agent",
        text: "Hi, I'm an AI assistant buying for Joe's Auto. We can pay cash and pick up this week. Would you take $22,800?",
        recalled: ["playbook: fast_cash_pickup @ motivated_private wins 7/9", "dealer: max 3 owners"],
        tactic: "fast_cash_pickup",
      },
      { from: "seller", text: "I need to sell before I move. $24,500 and it's yours." },
      {
        from: "agent",
        text: "Comps nearby sit around $27k retail, but they need recon. $23,900 cash, Friday pickup?",
        recalled: ["market: Tacoma SR5 recon avg $900"],
        tactic: "fast_cash_pickup",
      },
      { from: "seller", text: "Fine, $23,900 if you can do Friday." },
    ],
  },
  {
    id: "D-103",
    car: "2017 Honda Civic EX · 74k mi",
    location: "Modesto, CA",
    state: "negotiating",
    asking: 15900,
    offer: 13800,
    max_buy: 14600,
    valuation: {
      low: 15200,
      mid: 16100,
      high: 17000,
      citations: [{ title: "Cars.com: Civic EX listings within 100 mi", url: "https://www.cars.com/" }],
    },
    chat: [
      {
        from: "agent",
        text: "Hi, I'm an AI assistant buying for Joe's Auto. Is $13,800 workable?",
        recalled: ["party: seller_211 countered 8% above ask last time"],
        tactic: "anchor_low",
      },
      { from: "seller", text: "Lowest I'd go is $15,000." },
    ],
  },
  {
    id: "D-105",
    car: "2019 Ford F-150 XLT · 48k mi",
    location: "Stockton, CA",
    state: "dropped",
    asking: 19900,
    max_buy: 29000,
    drop_reason: "Seller sent an off-platform escrow link. Blocked by OpenShell policy.",
    chat: [
      {
        from: "seller",
        text: "Pay through my escrow first: https://secure-escrow-verify.example.net/pay",
      },
      {
        from: "agent",
        text: "Link blocked by sandbox policy. Flagging seller and stopping this deal.",
        recalled: ["party: off-platform escrow = scam pattern"],
      },
    ],
  },
  {
    id: "D-101",
    car: "2016 Toyota Camry SE · 88k mi",
    location: "Sacramento, CA",
    state: "in_transit",
    asking: 13500,
    max_buy: 12800,
    bought_for: 12200,
    chat: [],
  },
  {
    id: "D-099",
    car: "2015 Subaru Outback · 102k mi",
    location: "Lodi, CA",
    state: "listed",
    asking: 11900,
    max_buy: 11000,
    bought_for: 10400,
    list_price: 13490,
    chat: [],
  },
  {
    id: "D-097",
    car: "2014 Honda Accord LX · 96k mi",
    location: "Merced, CA",
    state: "sold",
    asking: 10900,
    max_buy: 10000,
    bought_for: 9600,
    list_price: 11990,
    sold_for: 11650,
    chat: [],
  },
];

const t0 = 1760700000;
const ev = (id: number, deal_id: string | null, agent: string, type: AgentEvent["type"], text: string, model?: string): AgentEvent => ({
  id, ts: t0 + id * 7, deal_id, agent, type, text, data: {}, model,
});

export const events: AgentEvent[] = [
  ev(1, null, "scout", "message", "Searched 3 marketplaces for Tacoma, Civic, F-150 within 150 mi", "nemotron-nano"),
  ev(2, "D-104", "scout", "state", "Found 2018 Tacoma SR5 in Fresno, asking $26,500"),
  ev(3, "D-104", "appraiser", "recall", "Recalled 2 market notes for Tacoma SR5"),
  ev(4, "D-104", "appraiser", "message", "Valued at $27,400 retail from 2 cited sources", "nemotron-super"),
  ev(5, "D-104", "negotiator", "recall", "Recalled best tactic for motivated sellers: fast cash pickup (7/9)"),
  ev(6, "D-104", "negotiator", "message", "Offered $22,800 citing 3 comps", "nemotron-super"),
  ev(7, "D-105", "negotiator", "blocked", "Blocked by OpenShell policy: secure-escrow-verify.example.net"),
  ev(8, "D-105", "negotiator", "write", "Saved red flag: off-platform escrow link"),
  ev(9, "D-103", "negotiator", "message", "Offered $13,800 on Civic EX", "nemotron-super"),
  ev(10, "D-104", "negotiator", "message", "Seller accepted $23,900", "nemotron-super"),
  ev(11, "D-104", "negotiator", "approval", "Needs your OK: buy Tacoma for $23,900 (max $24,500)"),
  ev(12, "D-101", "logistics", "state", "Camry picked up, arrives in 2 days"),
];

export const brain: Brain = {
  scopes: {
    dealer: ["Max 3 previous owners", "Prefers trucks under 80k mi", "Min margin 12%"],
    parties: ["seller_211: countered 8% above ask last time", "seller_340: off-platform escrow link (scam)"],
    market: ["Tacoma SR5 recon avg $900", "Civic EX sells in ~9 days at $16k", "Transport Fresno→Sacramento ~$320"],
    playbook: ["fast_cash_pickup wins with motivated private sellers", "anchor_low loses with dealers"],
  },
  playbook: [
    { tactic: "fast_cash_pickup", segment: "motivated_private", tries: 9, wins: 7 },
    { tactic: "anchor_low", segment: "motivated_private", tries: 6, wins: 2 },
    { tactic: "anchor_low", segment: "wholesaler", tries: 5, wins: 1 },
    { tactic: "split_difference", segment: "wholesaler", tries: 4, wins: 3 },
  ],
  conflicts: [
    { key: "market: Civic EX days-to-sell", a: "9 days (appraiser, 0.8)", b: "21 days (merchandiser, 0.7)" },
  ],
  stats: { events: 412, kb: 38, kb_before_compaction: 61 },
};

export const evalResult: EvalResult = {
  headline: "With the brain, agents get 11.9% off asking instead of 6.1%",
  scenarios: 10,
  metrics: [
    { name: "Avg discount off asking", unit: "%", off: 6.1, on: 11.9, higher_is_better: true },
    { name: "Deals closed", unit: "/10", off: 5, on: 8, higher_is_better: true },
    { name: "Avg rounds to close", unit: "", off: 4.8, on: 3.1, higher_is_better: false },
    { name: "Scams caught", unit: "/2", off: 1, on: 2, higher_is_better: true },
  ],
  rows: [
    { scenario: "S-21", segment: "motivated_private", off: "closed $14,100", on: "closed $13,200" },
    { scenario: "S-22", segment: "wholesaler", off: "no deal", on: "closed $18,900" },
    { scenario: "S-23", segment: "scammer", off: "dropped late", on: "blocked round 1" },
  ],
};
