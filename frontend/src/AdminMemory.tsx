import { useEffect, useState } from "react";

// Owner-only page at /admin?token=... Not linked from the dealer app. The backend checks the token.
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Arm = { n: number; close_rate: number; mean_saved_pct: number; surplus_captured_pct: number; mean_rounds: number; scams_blocked: number; scams: number };
type Data = {
  brain: { events: number; keys: Record<string, number>; conflicts: number; per_scope: Record<string, number> };
  eval: { seed: number; train_n: number; heldout_n: number; off: Arm; on: Arm; secs: number } | null;
  llm: Record<string, { calls: number; errors: number }>;
  youcom: { calls: number; cache_hits: number; errors: number; demo_mode: boolean };
  agents: { working: number; total: number; shift_phase: string; demo_names: boolean;
            agents: { name: string; role: string; status: "working" | "idle" }[] };
};

const pct = (n: number) => `${n.toFixed(1)}%`;

export default function AdminMemory() {
  // The token can come from the link or be typed here. It is kept in memory only, never stored.
  const [token, setToken] = useState(() => new URLSearchParams(window.location.search).get("token") ?? "");
  const [draft, setDraft] = useState("");
  const [data, setData] = useState<Data | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "ok" | "denied" | "offline">(token ? "loading" : "idle");

  useEffect(() => {
    if (!token) return;
    setState("loading");
    fetch(`${API}/admin/memory?token=${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (r.status === 403) return setState("denied");
        if (!r.ok) return setState("offline");
        setData(await r.json());
        setState("ok");
      })
      .catch(() => setState("offline"));
  }, [token]);

  if (state !== "ok" || !data) {
    return (
      <main className="content stack">
        <h1>Admin: memory and cost</h1>
        {state !== "loading" && (
          <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); setToken(draft.trim()); }}>
            <label htmlFor="admin-token">Admin token</label>
            <div className="row">
              <input id="admin-token" type="password" autoComplete="off" value={draft}
                onChange={(e) => setDraft(e.target.value)} placeholder="Paste your admin token"
                style={{ minWidth: 280, minHeight: 40, padding: "6px 12px", borderRadius: 999, border: "1px solid var(--line-strong)", font: "inherit" }} />
              <button className="primary" type="submit" disabled={!draft.trim()}>Open</button>
            </div>
          </form>
        )}
        <p className="muted">
          {state === "loading" && "Loading…"}
          {state === "idle" && "Enter the admin token to open this page."}
          {state === "denied" && "That token isn't accepted. Check it and try again."}
          {state === "offline" && "Can't reach the backend."}
        </p>
      </main>
    );
  }

  const { off, on } = data.eval ?? { off: null, on: null };
  const roundsChange = off && on && off.mean_rounds ? ((on.mean_rounds - off.mean_rounds) / off.mean_rounds) * 100 : null;
  const modelCalls = Object.values(data.llm).reduce((s, m) => s + m.calls, 0);
  const cacheShare = data.youcom.calls + data.youcom.cache_hits
    ? (data.youcom.cache_hits / (data.youcom.calls + data.youcom.cache_hits)) * 100 : 0;

  return (
    <main className="content stack">
      <header className="page-head">
        <h1>Admin: memory and cost</h1>
        <p>Owner only. Shows what the shared memory does for cost and quality. Not part of the dealer app.</p>
      </header>

      <section className="stack-sm" aria-labelledby="agents-head">
        <h2 id="agents-head">Agents working now</h2>
        <div className="summary">
          <div className="stat"><span className="value">{data.agents.working} of {data.agents.total}</span><span className="label">Agents working</span></div>
          <div className="stat"><span className="value">{data.agents.shift_phase}</span><span className="label">Shift phase</span></div>
        </div>
        <table className="list">
          <thead><tr><th>Name (demo)</th><th>Role</th><th>Status</th></tr></thead>
          <tbody>
            {data.agents.agents.map((a) => (
              <tr key={a.name}>
                <td data-label="Name">{a.name}</td>
                <td data-label="Role">{a.role}</td>
                <td data-label="Status" className={a.status === "working" ? "good" : "muted"}>{a.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small muted">Names are demo labels for the agents. The status is live from the shift and the deals.</p>
      </section>

      <section className="stack-sm" aria-labelledby="cost-head">
        <h2 id="cost-head">Memory on vs off (held-out eval)</h2>
        {off && on ? (
          <>
            <table className="list">
              <thead><tr><th>Measure</th><th>Memory off</th><th>Memory on</th><th>Change</th></tr></thead>
              <tbody>
                <tr><td data-label="Measure">Negotiation rounds per car</td><td data-label="Off" className="num">{off.mean_rounds.toFixed(2)}</td><td data-label="On" className="num">{on.mean_rounds.toFixed(2)}</td><td data-label="Change" className="num good">{roundsChange !== null ? `${roundsChange.toFixed(0)}%` : "—"}</td></tr>
                <tr><td data-label="Measure">Paid below asking</td><td data-label="Off" className="num">{pct(off.mean_saved_pct)}</td><td data-label="On" className="num">{pct(on.mean_saved_pct)}</td><td data-label="Change" className="num good">+{(on.mean_saved_pct - off.mean_saved_pct).toFixed(1)} pts</td></tr>
                <tr><td data-label="Measure">Surplus captured</td><td data-label="Off" className="num">{pct(off.surplus_captured_pct)}</td><td data-label="On" className="num">{pct(on.surplus_captured_pct)}</td><td data-label="Change" className="num good">+{(on.surplus_captured_pct - off.surplus_captured_pct).toFixed(1)} pts</td></tr>
                <tr><td data-label="Measure">Close rate</td><td data-label="Off" className="num">{pct(off.close_rate * 100)}</td><td data-label="On" className="num">{pct(on.close_rate * 100)}</td><td data-label="Change" className="num">—</td></tr>
              </tbody>
            </table>
            <p className="small muted">
              Held-out scenarios: {on.n} (seed {data.eval?.seed}, trained on {data.eval?.train_n}). Eval ran on the mock LLM.
              Fewer rounds means fewer model turns per car, which is the cost proxy here. Dollar cost is not measured yet:
              it needs one run with the live model on and token counts recorded.
            </p>
          </>
        ) : (
          <p className="empty">No eval result yet. Run the eval to fill this in.</p>
        )}
      </section>

      <section className="stack-sm" aria-labelledby="mem-head">
        <h2 id="mem-head">Memory in use</h2>
        <div className="summary">
          <div className="stat"><span className="value">{data.brain.events}</span><span className="label">Shared memory entries</span></div>
          <div className="stat"><span className="value">{data.brain.conflicts}</span><span className="label">Conflicting facts</span></div>
          <div className="stat"><span className="value">{Object.values(data.brain.keys).reduce((a, b) => a + b, 0)}</span><span className="label">Remembered keys</span></div>
        </div>
      </section>

      <section className="stack-sm" aria-labelledby="calls-head">
        <h2 id="calls-head">Model calls and searches (this server run)</h2>
        <div className="summary">
          <div className="stat"><span className="value">{modelCalls}</span><span className="label">Model calls</span></div>
          <div className="stat"><span className="value">{data.youcom.calls}</span><span className="label">Live searches</span></div>
          <div className="stat"><span className="value">{pct(cacheShare)}</span><span className="label">Searches answered from cache</span></div>
        </div>
        <p className="small muted">{data.youcom.demo_mode ? "Demo mode: searches read the cache, no live calls." : "Live mode."}</p>
      </section>
    </main>
  );
}
