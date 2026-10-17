import type { EvalResult } from "./types";

type Props = { result: EvalResult; onRun: () => void };

export default function EvalView({ result, onRun }: Props) {
  return (
    <>
      <section>
        <p className="muted small">
          The same {result.scenarios} sellers, run twice: once without team memory, once with it.
        </p>
        <h2 className="headline">{result.headline}</h2>
      </section>

      <section className="legend" aria-label="Key">
        <span><i className="swatch off" aria-hidden="true" />Without memory</span>
        <span><i className="swatch on" aria-hidden="true" />With memory</span>
      </section>

      <section className="metrics">
        {result.metrics.map((m) => {
          const max = Math.max(m.off, m.on) || 1;
          const better = m.higher_is_better ? m.on > m.off : m.on < m.off;
          return (
            <div key={m.name} className="metric">
              <div className="row">
                <strong>{m.name}</strong>
                <span className={better ? "good" : "muted small"}>
                  {better ? "Better with memory" : m.higher_is_better ? "Higher is better" : "Lower is better"}
                </span>
              </div>
              <Bar kind="off" value={m.off} max={max} unit={m.unit} label="Without memory" />
              <Bar kind="on" value={m.on} max={max} unit={m.unit} label="With memory" />
            </div>
          );
        })}
      </section>

      <section aria-labelledby="per-seller">
        <h2 id="per-seller">Seller by seller</h2>
        <table>
          <thead><tr><th>Seller</th><th>Type</th><th>Without memory</th><th>With memory</th></tr></thead>
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

      <section><button onClick={onRun}>Run the test again</button></section>
    </>
  );
}

function Bar({ kind, value, max, unit, label }: { kind: "off" | "on"; value: number; max: number; unit: string; label: string }) {
  return (
    <div className="barrow">
      <span className="small muted" style={{ width: 120 }}>{label}</span>
      <div className={`bar ${kind}`} role="img" aria-label={`${label}: ${value}${unit}`}>
        <div style={{ width: `${(value / max) * 100}%` }} />
      </div>
      <span>{value}{unit}</span>
    </div>
  );
}
