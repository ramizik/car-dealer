import { useEffect, useRef } from "react";
import { api } from "./api";
import { STAGES, money, profit, time } from "./format";
import type { AgentEvent, Deal } from "./types";
import { CHANNEL_LABELS } from "./channels";
import SellerTurn from "./SellerTurn";
import TurnBanner from "./TurnBanner";

type Props = {
  deal: Deal;
  events: AgentEvent[];
  onClose: () => void;
  onDecide: (id: string, yes: boolean) => void;
};


export default function DealPanel({ deal, events, onClose, onDecide }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const step = STAGES.findIndex((s) => s.state === deal.state);
  const history = events.filter((e) => e.deal_id === deal.id && e.type !== "recall" && e.type !== "write");
  const stopped = deal.state === "dropped";
  const memory = events.filter((e) => e.deal_id === deal.id && e.type === "write" && typeof e.data.artifact === "string");
  const lastAudio = deal.chat.map((t) => Boolean(t.audio_url)).lastIndexOf(true);

  // Escape closes, and focus starts on the close button so keyboard users are not lost behind the scrim.
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const progress = stopped || step < 0 ? 0 : ((step + 1) / STAGES.length) * 100;

  return (
    <div className="scrim" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="deal-title" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <div>
            <span className="muted small">{deal.id} · {deal.location}</span>
            <h2 id="deal-title">{deal.car}</h2>
          </div>
          <button ref={closeRef} onClick={onClose}>Close</button>
        </header>

        {stopped ? (
          <p className="notice danger">Stopped: {deal.drop_reason}</p>
        ) : (
          <>
            <p className="stage">
              Step {step + 1} of {STAGES.length}: <strong>{STAGES[step]?.label ?? "Found"}</strong>
            </p>
            <div className="progress" role="img" aria-label={`${Math.round(progress)}% through the process`}>
              <div style={{ width: `${progress}%` }} />
            </div>
          </>
        )}

        {!stopped && (deal.live || deal.turn) && <TurnBanner deal={deal} />}
        {!stopped && deal.turn?.who === "seller" && <SellerTurn dealId={deal.id} offer={deal.turn.offer} />}

        {deal.state === "awaiting_approval" && (
          <section aria-label="Decision needed">
            <div className="decision">
              <div>
                <h3>Buy for {money(deal.offer)}?</h3>
                <p>Your max is {money(deal.max_buy)}. Nothing is bought until you approve.</p>
              </div>
              <div className="actions">
                <button onClick={() => onDecide(deal.id, false)}>Decline</button>
                <button className="primary" onClick={() => onDecide(deal.id, true)}>Approve {money(deal.offer)}</button>
              </div>
            </div>
          </section>
        )}

        <dl className="facts-grid">
          <Num label="Asking" value={money(deal.asking)} />
          <Num label="Your max" value={money(deal.max_buy)} />
          <Num label="Our offer" value={money(deal.offer)} />
          <Num label="Paid" value={money(deal.bought_for)} />
          <Num label="Shipping" value={money(deal.shipping)} />
          <Num label="Listed at" value={money(deal.list_price)} />
          <Num label="Profit" value={money(profit(deal))} />
        </dl>

        {deal.valuation && <Valuation {...deal.valuation} />}

        {deal.listing && (
          <section aria-labelledby="listing">
            <h3 id="listing">Storefront listing</h3>
            <div className="listing-copy">
              <strong>{deal.listing.title}</strong>
              <p>{deal.listing.description}</p>
              <ul>{deal.listing.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
            </div>
          </section>
        )}

        {memory.length > 0 && (
          <section aria-labelledby="saved">
            <h3 id="saved">Saved to team memory</h3>
            <ul className="sources">{memory.map((e) => <li key={e.id} className="small">{e.text.replace("Saved to memory: ", "")}</li>)}</ul>
          </section>
        )}

        {deal.chat.length > 0 && (
          <section aria-labelledby="conversation">
            <h3 id="conversation">Conversation</h3>
            <div className="chat">
              {deal.chat.map((t, i) => (
                <div key={i} className={`bubble ${t.from === "agent" ? "ours" : ""}`}>
                  <span className="who">
                    {t.from === "agent" ? "You (via us)" : t.from === "buyer" ? "Buyer" : "Seller"}
                    {t.channel && <span className="tag channel">{CHANNEL_LABELS[t.channel] ?? t.channel}</span>}
                    {t.tactic && <span className="tag">{t.tactic.replace(/_/g, " ")}</span>}
                  </span>
                  <p>{t.text}</p>
                  {t.audio_url && (
                    // Autoplay only the newest clip while the agent's line is the one just spoken; browsers may still block it.
                    <audio controls preload="auto" src={api.clipUrl(t.audio_url)} autoPlay={i === lastAudio && deal.turn?.who === "seller"} />
                  )}
                  {t.recalled && t.recalled.length > 0 && (
                    <div className="memory">
                      Based on past deals
                      <div className="chips">
                        {t.recalled.map((r) => <span key={r} className="chip">{r}</span>)}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <section aria-labelledby="history">
          <h3 id="history">History</h3>
          {history.length === 0 && <p className="empty">Nothing recorded for this car yet.</p>}
          <ol className="history">
            {history.map((e) => (
              <li key={e.id} className={e.type === "blocked" ? "blocked" : ""}>
                <span className="who">{time(e.ts)}</span>
                {typeof e.data.channel === "string" && <span className="tag channel">{CHANNEL_LABELS[e.data.channel] ?? e.data.channel}</span>}
                {e.text}
              </li>
            ))}
          </ol>
        </section>
      </aside>
    </div>
  );
}

function Valuation({ low, mid, high, citations }: NonNullable<Deal["valuation"]>) {
  const span = high - low || 1;
  const at = Math.min(100, Math.max(0, ((mid - low) / span) * 100));
  return (
    <section aria-labelledby="market">
      <h3 id="market">Market value</h3>
      <p>Most likely <strong>{money(mid)}</strong>, usually between {money(low)} and {money(high)}.</p>
      <div className="range" role="img" aria-label={`Most likely ${money(mid)} within ${money(low)} to ${money(high)}`}>
        <span className="mid" style={{ left: `${at}%` }} />
      </div>
      <div className="range-labels"><span>{money(low)}</span><span>{money(high)}</span></div>
      <ul className="sources">
        {citations.map((c) => (
          <li key={c.url}>
            <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Num({ label, value }: { label: string; value: string }) {
  if (value === "—") return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
