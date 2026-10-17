import type { EvalResult } from "./types";

type Props = { result: EvalResult; onRun: () => void };

export default function EvalView({ result, onRun }: Props) {
  return (
    <div className="stack">
      <section>
        <p className="muted small">Same {result.scenarios} sellers the agents have never seen, run twice: once without memory, once with it.</p>
        <h2 className="headline">{result.headline}</h2>
      </section>

      <section className="legend">
        <span><i className="swatch off" /> Without brain</span>
        <span><i className="swatch on" /> With brain</span>
      </section>

      <section className="metrics">
        {result.metrics.map((m) => {
          const max = Math.max(m.off, m.on) || 1;
          const better = m.higher_is_better ? m.on > m.off : m.on < m.off;
          return (
            <div key={m.name} className="metric">
              <div className="row">
                <strong>{m.name}</strong>
                <span className={better ? "good" : "muted"}>{m.higher_is_better ? "higher is better" : "lower is better"}</span>
              </div>
              <Bar kind="off" value={m.off} max={max} unit={m.unit} />
              <Bar kind="on" value={m.on} max={max} unit={m.unit} />
            </div>
          );
        })}
      </section>

      <section>
        <h2>Per seller</h2>
        <table>
          <thead><tr><th>Seller</th><th>Type</th><th>Without brain</th><th>With brain</th></tr></thead>
          <tbody>
            {result.rows.map((r) => (
              <tr key={r.scenario}>
                <td>{r.scenario}</td>
                <td>{r.segment.replace(/_/g, " ")}</td>
                <td>{r.off}</td>
                <td>{r.on}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section><button onClick={onRun}>Run again</button></section>
    </div>
  );
}

function Bar({ kind, value, max, unit }: { kind: "off" | "on"; value: number; max: number; unit: string }) {
  return (
    <div className="barrow">
      <div className={`bar ${kind}`}><div style={{ width: `${(value / max) * 100}%` }} /></div>
      <span>{value}{unit}</span>
    </div>
  );
}
