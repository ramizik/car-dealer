// Reads return null when the backend is unreachable. The UI then says so; it never shows made-up data.
import type { AgentEvent, Brain, Deal, EvalResult, Health, Inventory, OnboardingQuestion } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return (await r.json()) as T;
  } catch {
    return null;
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

// Seller answers: the backend replies {ok, error?}. Speech can take a few seconds, so the timeout is longer.
type AnswerResult = { ok: boolean; error?: string };
async function answer(path: string, init: RequestInit): Promise<AnswerResult> {
  try {
    const r = await fetch(`${API}${path}`, { method: "POST", ...init, signal: AbortSignal.timeout(30000) });
    const body = (await r.json().catch(() => ({}))) as AnswerResult;
    return r.ok ? body : { ok: false, error: body.error ?? `HTTP ${r.status}` };
  } catch {
    return { ok: false, error: "Backend unreachable" };
  }
}

export const api = {
  health: () => get<Health>("/health"),
  deals: () => get<Deal[]>("/deals"),
  events: (since = 0) => get<AgentEvent[]>(`/events?since=${since}`),
  brain: () => get<Brain>("/brain"),
  inventory: () => get<Inventory>("/inventory"),
  eval: () => get<EvalResult>("/eval"),
  saveSetup: (answers: Record<string, string[]>) => post("/onboarding/answers", { answers }),
  onboardingQuestions: async () => (await get<OnboardingQuestion[]>("/onboarding/questions")) ?? [],
  startDemo: () => post("/demo/start"),
  stopShift: () => post("/shift/stop"),
  approve: (id: string, yes: boolean, car = "", reason = "") => post(`/deals/${id}/approve`, { yes, car, reason }),
  sale: (id: string, yes: boolean) => post(`/deals/${id}/sale`, { yes }),
  sendSellerAudio: (id: string, wav: Blob) =>
    answer(`/deals/${id}/seller-audio`, { body: wav, headers: { "Content-Type": "audio/wav" } }),
  sendSellerText: (id: string, text: string) =>
    answer(`/deals/${id}/seller-text`, { body: JSON.stringify({ text }), headers: { "Content-Type": "application/json" } }),
  clipUrl: (path: string) => `${API}${path}`,
  runEval: () => post("/eval/run"),
  storefrontUrl: `${API}/storefront`,
  loadSnapshot: (name: "cold" | "warm") => post(`/brain/load/${name}`),
};
