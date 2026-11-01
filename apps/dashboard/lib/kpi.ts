import type { Item, Risk } from "./types";

/** Cost and margin shares used by the backend planner (stated in the UI). */
export const COST_SHARE = 0.6;
export const MARGIN_SHARE = 0.4;

export type Currency = Item["currency"];

export interface Money {
  EUR: number;
  CHF: number;
}

export const zeroMoney = (): Money => ({ EUR: 0, CHF: 0 });

export interface ItemMetrics {
  key: string;
  item: Item;
  orderUnits: number;
  orderCost: number;
  wasteCost: number;
  lostMargin: number;
  /** Cost of stock whose use-by date is within one day. */
  atRiskCost: number;
  worstRisk: Risk;
  /** Ranking value for the attention list. */
  attention: number;
}

export const itemKey = (item: Pick<Item, "store_id" | "sku">) =>
  `${item.store_id}|${item.sku}`;

const RISK_ORDER: Record<Risk, number> = { low: 0, medium: 1, high: 2 };

export function worstRisk(item: Item): Risk {
  return item.lots.reduce<Risk>(
    (worst, lot) => (RISK_ORDER[lot.risk] > RISK_ORDER[worst] ? lot.risk : worst),
    "low",
  );
}

export function itemMetrics(item: Item, costShare: number = COST_SHARE): ItemMetrics {
  const cost = item.unit_price * costShare;
  const marginShare = 1 - costShare;
  const p = item.proposal;
  const atRiskUnits = item.lots
    .filter((l) => l.days_left <= 1)
    .reduce((sum, l) => sum + l.quantity, 0);
  const wasteCost = p.outlook_waste_units * cost;
  const lostMargin = p.outlook_lost_units * item.unit_price * marginShare;
  return {
    key: itemKey(item),
    item,
    orderUnits: p.recommended_order_units,
    orderCost: p.recommended_order_units * cost,
    wasteCost,
    lostMargin,
    atRiskCost: atRiskUnits * cost,
    worstRisk: worstRisk(item),
    attention: wasteCost + lostMargin,
  };
}

export interface Totals {
  orderCost: Money;
  wasteCost: Money;
  lostMargin: Money;
  atRiskCost: Money;
  itemsToOrder: number;
  items: number;
}

export function totals(metrics: ItemMetrics[]): Totals {
  const t: Totals = {
    orderCost: zeroMoney(),
    wasteCost: zeroMoney(),
    lostMargin: zeroMoney(),
    atRiskCost: zeroMoney(),
    itemsToOrder: 0,
    items: metrics.length,
  };
  for (const m of metrics) {
    const c = m.item.currency;
    t.orderCost[c] += m.orderCost;
    t.wasteCost[c] += m.wasteCost;
    t.lostMargin[c] += m.lostMargin;
    t.atRiskCost[c] += m.atRiskCost;
    if (m.orderUnits > 0) t.itemsToOrder += 1;
  }
  return t;
}

/** Highest-value problems first. */
export function attentionList(metrics: ItemMetrics[], limit = 6): ItemMetrics[] {
  return [...metrics]
    .filter((m) => m.attention > 0 || m.atRiskCost > 0)
    .sort((a, b) => b.attention + b.atRiskCost - (a.attention + a.atRiskCost))
    .slice(0, limit);
}
