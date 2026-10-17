// Shapes follow the API contract in agents/plans/roadmap.md (§P2).

export type DealState =
  | "sourced"
  | "appraised"
  | "negotiating"
  | "awaiting_approval"
  | "bought"
  | "in_transit"
  | "delivered"
  | "listed"
  | "sold"
  | "dropped";

export type EventType = "message" | "recall" | "write" | "state" | "outreach" | "blocked" | "approval" | "error";

export type AgentEvent = {
  id: number;
  ts: number;
  deal_id: string | null;
  agent: string;
  type: EventType;
  text: string;
  data: Record<string, unknown>;
  model?: string;
};

export type Citation = { title: string; url: string };

export type ChatTurn = {
  from: "agent" | "seller" | "buyer";
  text: string;
  recalled?: string[];
  tactic?: string;
  channel?: string;
};

export type Deal = {
  id: string;
  car: string;
  location: string;
  state: DealState;
  asking: number;
  offer?: number;
  max_buy: number;
  bought_for?: number;
  list_price?: number;
  sold_for?: number;
  valuation?: { low: number; mid: number; high: number; citations: Citation[] };
  chat: ChatTurn[];
  drop_reason?: string;
  listing_url?: string;
};

export type Health = {
  ok: boolean;
  demo_mode: boolean;
  brain_enabled: boolean;
  sandboxed: boolean;
  shift_running?: boolean;
  dealer_name?: string;
};

export type Conflict = { key: string; a: string; b: string };

export type PlaybookRow = { tactic: string; segment: string; tries: number; wins: number };

export type Brain = {
  scopes: { dealer: string[]; parties: string[]; market: string[]; playbook: string[] };
  playbook: PlaybookRow[];
  conflicts: Conflict[];
  stats: { events: number; kb: number; kb_before_compaction?: number };
};

export type EvalMetric = { name: string; unit: string; off: number; on: number; higher_is_better: boolean };

export type EvalResult = {
  headline: string;
  scenarios: number;
  metrics: EvalMetric[];
  rows: { scenario: string; segment: string; off: string; on: string }[];
};

export type OnboardingOption = { value: string; label: string; recommended?: boolean };
export type OnboardingQuestion = {
  id: string;
  ask: string;
  type: "single" | "multi";
  options: OnboardingOption[];
};
