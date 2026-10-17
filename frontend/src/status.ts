import { money } from "./format";
import type { Deal } from "./types";

// One plain sentence per deal: what the team is doing right now, and whether a person has to act.
// The Shift page and the deal drawer both read from here, so they never disagree.
export type Now = {
  tone: "agent" | "you" | "done" | "stopped";
  title: string;
  detail: string;
  action?: "seller" | "approve" | "sale";
};

export function nowFor(deal: Deal): Now {
  if (deal.state === "dropped") {
    return { tone: "stopped", title: "Stopped", detail: deal.drop_reason ?? "No deal." };
  }
  if (deal.turn?.who === "seller") {
    return { tone: "you", title: "Your turn: the seller is on the line", detail: "Record what they said, or type it.", action: "seller" };
  }
  if (deal.state === "awaiting_approval") {
    return {
      tone: "you",
      title: "Waiting for your OK to buy",
      detail: `Agreed ${money(deal.offer)}. Your max is ${money(deal.max_buy)}. Nothing is bought until you approve.`,
      action: "approve",
    };
  }
  if (deal.state === "awaiting_sale") {
    return {
      tone: "you",
      title: "Waiting for your OK to sell",
      detail: `A buyer accepted ${money(deal.sale_offer)}. Nothing sells until you say yes.`,
      action: "sale",
    };
  }
  if (deal.state === "sold") {
    return { tone: "done", title: "Sold", detail: "Finished. Nothing needed from you." };
  }
  if (deal.state === "negotiating") {
    return {
      tone: "agent",
      title: "Agent is negotiating",
      detail: deal.turn?.who === "system" ? "Agent is replying to the seller." : "Agent is talking to the seller.",
    };
  }
  if (deal.state === "sourced" || deal.state === "appraised") {
    return { tone: "agent", title: "Agent is checking the car", detail: deal.state === "sourced" ? "Valuing it against the market." : "Next: talk to the seller." };
  }
  return { tone: "done", title: "Team is handling it", detail: "Shipping, listing or selling. Nothing needed from you." };
}

// Why the team made its move, in one line: the numbers behind the decision.
export function decisionLine(deal: Deal): string {
  if (deal.state === "dropped") {
    const offer = deal.offer === undefined ? "" : ` Last offer ${money(deal.offer)}.`;
    return `Stopped.${offer} ${deal.drop_reason ?? ""}`.trim();
  }
  if (deal.offer === undefined) return `Asking ${money(deal.asking)}. No offer yet.`;
  return `Asking ${money(deal.asking)}, we offered ${money(deal.offer)}, your max is ${money(deal.max_buy)}.`;
}

export const needsYou = (d: Deal) =>
  d.turn?.who === "seller" || d.state === "awaiting_approval" || d.state === "awaiting_sale";
