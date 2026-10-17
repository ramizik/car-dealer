// Reads return null when the backend is unreachable. The UI then says so; it never shows made-up data.
import type { AgentEvent, Brain, Deal, EvalResult, Health, OnboardingQuestion } from "./types";

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

export const api = {
  health: () => get<Health>("/health"),
  deals: () => get<Deal[]>("/deals"),
  events: (since = 0) => get<AgentEvent[]>(`/events?since=${since}`),
  brain: () => get<Brain>("/brain"),
  eval: () => get<EvalResult>("/eval"),
  saveSetup: (answers: Record<string, string[]>) => post("/onboarding/answers", { answers }),
  onboardingQuestions: async () => (await get<OnboardingQuestion[]>("/onboarding/questions")) ?? [],
  startShift: (max_deals: number) => post("/shift/start", { max_deals }),
  stopShift: () => post("/shift/stop"),
  approve: (id: string, yes: boolean, car = "", reason = "") => post(`/deals/${id}/approve`, { yes, car, reason }),
  storefrontUrl: `${API}/storefront`,
  loadSnapshot: (name: "cold" | "warm") => post(`/brain/load/${name}`),
};
