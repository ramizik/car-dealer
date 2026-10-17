import { useState, type ReactNode } from "react";
import type { Deal, DealState } from "./types";

export type Column = { label: string; render: (d: Deal) => ReactNode; numeric?: boolean };
export type Filter = { id: string; label: string; states: DealState[] };

type Props = {
  title: string;
  intro: string;
  deals: Deal[];
  filters: Filter[];
  columns: Column[];
  empty: string;
  onOpen: (id: string) => void;
};

// One list pattern for Buying, Inventory and Selling: filter chips, then a table that becomes cards on a phone.
export default function DealsList({ title, intro, deals, filters, columns, empty, onOpen }: Props) {
  const [active, setActive] = useState(filters[0].id);
  const filter = filters.find((f) => f.id === active) ?? filters[0];
  const rows = deals.filter((d) => filter.states.includes(d.state));

  return (
    <div className="stack">
      <header className="page-head">
        <h1>{title}</h1>
        <p>{intro}</p>
      </header>

      <div className="chips-row" role="group" aria-label="Filter">
        {filters.map((f) => {
          const n = deals.filter((d) => f.states.includes(d.state)).length;
          return (
            <button key={f.id} className="chip-btn" aria-pressed={f.id === active} onClick={() => setActive(f.id)}>
              {f.label} <span className="count">{n}</span>
            </button>
          );
        })}
      </div>

      {rows.length === 0 ? (
        <p className="empty-card">{empty}</p>
      ) : (
        <table className="list">
          <thead>
            <tr>
              <th>Car</th>
              {columns.map((c) => <th key={c.label} className={c.numeric ? "num" : ""}>{c.label}</th>)}
              <th><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id} onClick={() => onOpen(d.id)}>
                <td data-label="Car">
                  <span className="car">{d.car}</span>
                  <span className="muted small">{d.location}</span>
                </td>
                {columns.map((c) => (
                  <td key={c.label} data-label={c.label} className={c.numeric ? "num" : ""}>{c.render(d)}</td>
                ))}
                <td className="open-cell">
                  <button className="quiet" onClick={(e) => { e.stopPropagation(); onOpen(d.id); }} aria-label={`Open ${d.car}`}>
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
