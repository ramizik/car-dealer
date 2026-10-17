// Every read falls back to fixtures, so a dead backend shows sample data, never a blank screen.
import * as fx from "./fixtures";
import type { AgentEvent, Brain, Deal, EvalResult, Health } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Loaded<T> = { data: T; offline: boolean };

async function get<T>(path: string, fallback: T): Promise<Loaded<T>> {
  try {
    const r = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return { data: (await r.json()) as T, offline: false };
  } catch {
    return { data: fallback, offline: true };
  }
}

async function post(path: string, body?: unknown): Promise<boolean> {
  try {
    const r = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    });
    return r.ok;
  } catch {
    return false;
  }
}

export const api = {
  health: () => get<Health>("/health", fx.health),
  deals: () => get<Deal[]>("/deals", fx.deals),
  events: () => get<AgentEvent[]>("/events?since=0", fx.events),
  brain: () => get<Brain>("/brain", fx.brain),
  eval: () => get<EvalResult>("/eval", fx.evalResult),
  startShift: () => post("/shift/start", { max_deals: 5 }),
  stopShift: () => post("/shift/stop"),
  approve: (id: string, yes: boolean) => post(`/deals/${id}/approve`, { yes }),
  loadSnapshot: (name: "cold" | "warm") => post(`/brain/load/${name}`),
  runEval: () => post("/eval/run"),
};
