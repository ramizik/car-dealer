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

export type EventType = "message" | "recall" | "write" | "state" | "outreach" | "blocked" | "approval" | "error" | "skill" | "callback";

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

export type ShiftStatus = {
  running: boolean;
  n: number;
  cap: number;
  started: number | null;
  ended: number | null;
  phase: string;
  deal: string | null;
};

export type LlmTier = { model: string; calls?: number; errors?: number; avg_latency: number | null };

export type Health = {
  ok: boolean;
  demo_mode: boolean;
  brain_enabled: boolean;
  llm_live?: boolean;
  sandboxed: boolean;
  shift_running?: boolean;
  shift?: ShiftStatus;
  dealer_name?: string;
  llm?: Record<string, LlmTier>;
};

export type PlaybookRow = { tactic: string; segment: string; tries: number; wins: number; rate?: number };

export type BrainEntry = {
  facts: Record<string, { value: unknown; confidence: number; source: string; agent: string }>;
  obs: Record<string, { median: number; n: number; sources: string[] }>;
  counters: Record<string, unknown>;
  notes: { text: string; confidence: number; agent: string }[];
  ts: number;
};

export type Brain = {
  scopes: Record<"dealer" | "party" | "market" | "playbook", Record<string, BrainEntry>>;
  conflicts: { scope: string; key: string; attr: string; values: string[]; chosen: unknown }[];
  playbook: PlaybookRow[];
  stats: { enabled: boolean; events: number; bytes: number; per_scope: Record<string, number>; keys: Record<string, number>; conflicts: number };
};

export type EvalSide = {
  n: number; closed: number; legit: number; close_rate: number; mean_saved_pct: number;
  surplus_captured_pct: number; mean_rounds: number; scams_blocked: number; scams: number; correct: number;
};

export type EvalResult = {
  missing?: boolean;
  seed?: number;
  train_n?: number;
  heldout_n?: number;
  off?: EvalSide;
  on?: EvalSide;
  train?: EvalSide;
  playbook?: PlaybookRow[];
  secs?: number;
  ran_at?: number;
};

export type OnboardingOption = { value: string; label: string; recommended?: boolean };
export type OnboardingQuestion = {
  id: string;
  ask: string;
  type: "single" | "multi";
  options: OnboardingOption[];
};
