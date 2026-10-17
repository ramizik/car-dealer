import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Check = { check: string; pass: boolean; reason: string };
type Step = { iter: number; output: string; results: Check[]; decision: string };
type Result = { goal: string; status: string; checks: string[]; output: string; trace: Step[] };

export default function App() {
  const [goal, setGoal] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [lessons, setLessons] = useState<string[]>([]);
  const [error, setError] = useState("");

  const refreshMemory = () =>
    fetch(`${API}/memory`).then((r) => r.json()).then((m) => setLessons(m.lessons)).catch(() => {});

  useEffect(() => { refreshMemory(); }, []);

  const go = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await fetch(`${API}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
      refreshMemory();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 800, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>dealer</h1>
      <p>One-line goal in. Agent team defines done, works, verifies, loops.</p>
      <input
        style={{ width: "75%", padding: 8 }}
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        placeholder="Goal..."
      />
      <button onClick={go} disabled={loading || !goal} style={{ padding: 8, marginLeft: 8 }}>
        {loading ? "Running..." : "Run"}
      </button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {result && (
        <>
          <h2>Status: {result.status}</h2>
          <h3>Definition of done</h3>
          <ul>{result.checks.map((c, i) => <li key={i}>{c}</li>)}</ul>
          <h3>Trace</h3>
          {result.trace.map((s) => (
            <details key={s.iter} open={s.iter === result.trace.length}>
              <summary>Iter {s.iter} - {s.decision}</summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>{s.output}</pre>
              <ul>
                {s.results.map((r, i) => (
                  <li key={i}>{r.pass ? "PASS" : "FAIL"} - {r.check}: {r.reason}</li>
                ))}
              </ul>
            </details>
          ))}
        </>
      )}

      <h3>Shared memory ({lessons.length})</h3>
      <ul>{lessons.map((l, i) => <li key={i}>{l}</li>)}</ul>
    </div>
  );
}
