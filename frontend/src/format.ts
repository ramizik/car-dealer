import type { Deal, DealState } from "./types";

export const money = (n?: number) => (n === undefined ? "—" : `$${Math.round(n).toLocaleString("en-US")}`);

export const time = (ts: number) =>
  new Date(ts * 1000).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

// Demo clock: 8 shop hours (8:00 AM–4:00 PM) spread across one shift of real seconds.
export const SHIFT_HOURS = 8;
export const SHIFT_SECS_DEFAULT = 300;

export type ShopAnchor = { started: number | null; shift_secs?: number };

export const shopClock = (minutes: number) => {
  const t = 8 * 60 + Math.max(0, Math.floor(minutes));
  const hour = Math.floor(t / 60) % 24;
  const m = t % 60;
  return `${((hour + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
};

/** Shop minutes since 8:00 AM, or null when this timestamp is outside the current shift. */
export function shopMinute(ts: number, shift: ShopAnchor | null | undefined): number | null {
  const started = shift?.started;
  const secs = shift?.shift_secs || SHIFT_SECS_DEFAULT;
  if (started == null || ts < started) return null;
  const p = Math.min(1, (ts - started) / secs);
  return Math.floor(p * SHIFT_HOURS * 60);
}

type Timed = { id: number; ts: number; deal_id?: string | null };

/**
 * Shop-clock label for each event. Events for one car that land in the same shop minute
 * each move forward one minute, so a fast deal still reads as a progression through the day.
 */
export function shopLabelMap(events: Timed[], shift: ShopAnchor | null | undefined): Map<number, string> {
  const groups = new Map<string, Timed[]>();
  for (const e of events) {
    const key = e.deal_id ?? "";
    const list = groups.get(key);
    if (list) list.push(e);
    else groups.set(key, [e]);
  }
  const labels = new Map<number, string>();
  for (const list of groups.values()) {
    const ordered = [...list].sort((a, b) => a.ts - b.ts || a.id - b.id);
    let prev = -1;
    for (const e of ordered) {
      const base = shopMinute(e.ts, shift);
      if (base == null) continue;
      const mins = Math.max(base, prev + 1);
      prev = mins;
      labels.set(e.id, shopClock(mins));
    }
  }
  return labels;
}

export const eventTime = (e: Timed, labels: Map<number, string>) => labels.get(e.id) ?? time(e.ts);

// Plain-language names for each pipeline state, in order.
export const STAGES: { state: DealState; label: string }[] = [
  { state: "sourced", label: "Found" },
  { state: "appraised", label: "Valued" },
  { state: "negotiating", label: "Negotiating" },
  { state: "awaiting_approval", label: "Needs your OK" },
  { state: "bought", label: "Bought" },
  { state: "in_transit", label: "Shipping" },
  { state: "delivered", label: "On the lot" },
  { state: "listed", label: "For sale" },
  { state: "awaiting_sale", label: "Sale needs your OK" },
  { state: "sold", label: "Sold" },
];

export const stageLabel = (s: DealState) => (s === "dropped" ? "Stopped" : STAGES.find((x) => x.state === s)!.label);

// The board groups the 9 states into the 4 questions a dealer asks.
export const COLUMNS: { title: string; hint: string; states: DealState[] }[] = [
  { title: "Buying", hint: "Agents are finding, valuing and negotiating", states: ["sourced", "appraised", "negotiating", "awaiting_approval"] },
  { title: "Coming in", hint: "Paid for, on the way to you", states: ["bought", "in_transit", "delivered"] },
  { title: "For sale", hint: "Listed on your storefront", states: ["listed", "awaiting_sale"] },
  { title: "Sold", hint: "Closed deals", states: ["sold"] },
];

export const profit = (d: Deal) => (d.sold_for !== undefined && d.bought_for !== undefined ? d.sold_for - d.bought_for : undefined);

// The single number that matters most at each stage.
export function keyNumber(d: Deal): string {
  if (d.state === "sold") return `Sold ${money(d.sold_for)} · +${money(profit(d))}`;
  if (d.state === "listed") return `Listed ${money(d.list_price)} · paid ${money(d.bought_for)}`;
  if (d.bought_for !== undefined) return `Paid ${money(d.bought_for)}`;
  if (d.offer !== undefined) return `Offer ${money(d.offer)} · asks ${money(d.asking)}`;
  return `Asks ${money(d.asking)}`;
}

// Plain names for agents in activity and history.
const AGENT_NAMES: Record<string, string> = {
  scout: "Scout",
  appraiser: "Valuer",
  negotiator: "Buyer",
  seller: "Seller",
  seller_agent: "Sales desk",
  logistics: "Shipping",
  librarian: "Memory",
  merchandiser: "Listings",
};
export const agentName = (a: string) => AGENT_NAMES[a] ?? a;

export const greeting = (d = new Date()) => (d.getHours() < 12 ? "Good morning" : d.getHours() < 18 ? "Good afternoon" : "Good evening");

// Craigslist cannot be posted to automatically (no API, CAPTCHA on posting). We draft the ad and
// link to the Stockton posting page; a person reviews it and posts it themselves.
export const CRAIGSLIST_POST = "https://stockton.craigslist.org/";

export function craigslistDraft(d: Deal): { title: string; price: string; body: string } {
  const price = d.list_price ? money(d.list_price) : "Ask me";
  const title = `${d.car.split(" · ")[0]} - ${price}`;
  const body = [
    `${d.car}, ${price}.`,
    "Inspected and detailed. Clean title. Call or message to see it.",
    "Stockton, CA.",
  ].join("\n");
  return { title, price, body };
}
