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
  audio_url?: string;
};

// Whose move it is on a live deal. Null means nobody is waiting: the team is working.
export type Turn = {
  who: "system" | "seller" | "owner";
  action: "call" | "answer" | "reply" | "approve";
  since: number;
  offer?: number;
} | null;

export type Deal = {
  id: string;
  car: string;
  location: string;
  state: DealState;
  asking: number;
  offer?: number;
  max_buy: number;
  max_profit?: number; // profit if we pay exactly max_buy
  bought_for?: number;
  list_price?: number;
  sold_for?: number;
  valuation?: { low: number; mid: number; high: number; citations: Citation[]; research?: { low: number; mid: number; high: number }; issues?: string[] };
  chat: ChatTurn[];
  live?: boolean;
  turn?: Turn;
  drop_reason?: string;
  listing_url?: string;
  shipping?: number;
  ship_days?: number;
  listing?: { title: string; description: string; bullets: string[] };
};

export type ShiftStatus = {
  running: boolean;
  n: number;
  cap: number;
  started: number | null;
  ended: number | null;
  phase: string;
  deal: string | null;
  continuous?: boolean;
  live?: boolean;
  background?: number;
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
  notes: { text: string; confidence: number; agent: string; private_to?: string[] }[];
  ts: number;
};

export type Brain = {
  scopes: Record<"dealer" | "party" | "market" | "playbook", Record<string, BrainEntry>>;
  conflicts: { scope: string; key: string; attr: string; values: string[]; chosen: unknown }[];
  playbook: PlaybookRow[];
  stats: { enabled: boolean; events: number; bytes: number; per_scope: Record<string, number>; keys: Record<string, number>; conflicts: number };
  tiers?: { private_chats: number; shared_writes: number; private_writes: number; lessons: string[]; mistakes: string[]; vectors?: { memories: number; kb: number; embedders: string[] } };
  last_tidy?: { ts: number; events_before: number; events_after: number; kb_before: number; kb_after: number; applied: boolean; lessons: number } | null;
};

export type EvalRow = {
  id: string; persona: string; segment: string; tactic: string; closed: boolean; price: number | null;
  ask: number; floor: number; rounds: number; dropped: string; scam: boolean; correct: boolean;
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
  rows?: { off: EvalRow[]; on: EvalRow[] };
  running?: boolean;
};

export type OnboardingOption = { value: string; label: string; recommended?: boolean };
export type OnboardingQuestion = {
  id: string;
  ask: string;
  type: "single" | "multi";
  options: OnboardingOption[];
};

// Cars to sell from a public listing source (Craigslist), shown on the Selling page.
export type InventoryItem = { title: string; price: number | null; location: string; url: string };
export type Inventory = { source: string; count: number; listings: InventoryItem[] };
