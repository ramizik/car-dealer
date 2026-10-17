import type { Deal, Turn } from "./types";

// Who has the move on a deal, in words a person in the room can read from across the table.
// Nobody's turn means the team is working on its own: the banner says so instead of going blank.
const PARTS = ["Agent", "Seller", "You"] as const;

export function turnParty(turn: Turn): number {
  if (!turn) return -1;
  if (turn.who === "seller") return 1;
  if (turn.who === "owner") return 2;
  return 0;
}

export function turnHeadline(deal: Deal): { pill: string; text: string; tone: "agent" | "seller" | "owner" | "idle" } {
  const t = deal.turn;
  if (!t) return { pill: "Team working", text: "Nobody needs to act on this car right now.", tone: "idle" };
  if (t.who === "seller") return { pill: "YOUR TURN", text: "The seller is on the line. Record what they said.", tone: "seller" };
  if (t.who === "owner") return { pill: "YOUR TURN", text: `Approve or decline the buy at ${t.offer ? `$${t.offer.toLocaleString("en-US")}` : "the agreed price"}.`, tone: "owner" };
  return {
    pill: "AGENT",
    text: t.action === "call" ? "The agent is calling the seller. Listen to the opening line." : "The agent is replying to the seller.",
    tone: "agent",
  };
}

export default function TurnBanner({ deal }: { deal: Deal }) {
  const head = turnHeadline(deal);
  const at = turnParty(deal.turn ?? null);
  return (
    <section className={`turn turn-${head.tone}`} aria-label="Whose turn it is" role="status">
      <div className="turn-head">
        <span className="turn-pill">{head.pill}</span>
        <span>{head.text}</span>
      </div>
      <ol className="turn-track">
        {PARTS.map((p, i) => (
          <li key={p} className={i === at ? "now" : i < at ? "done" : ""} aria-current={i === at ? "step" : undefined}>
            {p}
          </li>
        ))}
      </ol>
    </section>
  );
}
