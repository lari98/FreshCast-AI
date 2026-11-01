import type { Item } from "./types";

/**
 * Markdown (price cut) what-if for stock that is about to expire.
 * Everything here is an ASSUMPTION model, not a forecast of price response:
 * demand during the cut rises by `elasticity * markdown` (e.g. 1.5 * 30 % = +45 %).
 * A person decides on any price action.
 */

export interface LotExcess {
  lotId: string;
  quantity: number;
  daysLeft: number;
  /** Units of this lot that the forecast says will NOT sell before use-by (FEFO). */
  excess: number;
  /** Forecast units sold from this lot window at normal price. */
  baseline: number;
}

/** Per lot: how many units expire unsold, selling oldest stock first. */
export function lotExcess(item: Item): LotExcess[] {
  const future = item.series.filter((p) => p.actual === null);
  const lots = [...item.lots].sort((a, b) => a.use_by.localeCompare(b.use_by));
  let consumed = 0;
  return lots.map((lot) => {
    const window = future.filter((p) => p.is_open && p.date <= lot.use_by);
    const demandUntilUseBy = window.reduce((s, p) => s + p.point, 0);
    const available = Math.max(0, demandUntilUseBy - consumed);
    const sold = Math.min(lot.quantity, available);
    consumed += lot.quantity;
    return {
      lotId: lot.lot_id, quantity: lot.quantity, daysLeft: lot.days_left,
      excess: Math.max(0, lot.quantity - available), baseline: sold,
    };
  });
}

export interface Outcome {
  extraUnits: number;
  /** Revenue gain minus the margin given away on units that would sell anyway. */
  net: number;
}

export function markdownOutcome(
  price: number, rows: LotExcess[], markdown: number, elasticity: number,
): Outcome {
  let extra = 0;
  let givenAway = 0;
  let recovered = 0;
  for (const r of rows) {
    if (r.excess <= 0) continue;
    const added = Math.min(r.excess, r.baseline * elasticity * markdown);
    extra += added;
    recovered += added * price * (1 - markdown);
    givenAway += r.baseline * price * markdown;
  }
  return { extraUnits: extra, net: recovered - givenAway };
}

export const MARKDOWN_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7] as const;

/** Markdown from the grid with the highest net benefit, or null if none helps. */
export function bestMarkdown(
  price: number, rows: LotExcess[], elasticity: number,
): { markdown: number; outcome: Outcome } | null {
  let best: { markdown: number; outcome: Outcome } | null = null;
  for (const m of MARKDOWN_GRID) {
    const outcome = markdownOutcome(price, rows, m, elasticity);
    if (outcome.net > 0 && (!best || outcome.net > best.outcome.net)) best = { markdown: m, outcome };
  }
  return best;
}
