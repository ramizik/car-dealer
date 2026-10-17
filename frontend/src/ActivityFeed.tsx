import { useState } from "react";
import { eventTime, shopLabelMap, type ShopAnchor } from "./format";
import type { AgentEvent } from "./types";
import { CHANNEL_LABELS } from "./channels";

type Props = { events: AgentEvent[]; onOpen: (dealId: string) => void; limit?: number; shift?: ShopAnchor | null };

const isAttention = (e: AgentEvent) => e.type === "blocked" || e.type === "approval" || e.type === "error";

// Newest first. "Needs attention" hides routine steps so problems are easy to spot.
export default function ActivityFeed({ events, onOpen, limit, shift }: Props) {
  const [onlyAttention, setOnlyAttention] = useState(false);
  const times = shopLabelMap(events, shift);
  const all = [...events].reverse().filter((e) => e.type !== "recall" && e.type !== "write");  // hide internal steps
  const shown = (onlyAttention ? all.filter(isAttention) : all).slice(0, limit);

  return (
    <section className="panel" aria-labelledby="activity">
      <div className="panel-head">
        <h2 id="activity">Latest updates</h2>
        <div className="seg" role="group" aria-label="Filter activity">
          <button aria-pressed={!onlyAttention} onClick={() => setOnlyAttention(false)}>All</button>
          <button aria-pressed={onlyAttention} onClick={() => setOnlyAttention(true)}>Problems</button>
        </div>
      </div>
      {shown.length === 0 && (
        <p className="empty">{all.length === 0 ? "No updates yet. Start buying to see progress here." : "No problems right now."}</p>
      )}
      <ol className="feed">
        {shown.map((e) => (
          <li key={e.id} className={e.type === "blocked" ? "blocked" : e.type === "approval" ? "attn" : ""}>
            <span className="who">
              {eventTime(e, times)}
              {e.type === "blocked" && " · Blocked"}
              {typeof e.data.channel === "string" && <span className="tag channel">{CHANNEL_LABELS[e.data.channel] ?? e.data.channel}</span>}
            </span>
            {e.deal_id ? (
              <button className="feed-link" onClick={() => onOpen(e.deal_id!)}>{e.text}</button>
            ) : (
              <span>{e.text}</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
