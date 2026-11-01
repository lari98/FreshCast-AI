import { COST_SHARE } from "./kpi";
import type { ItemMetrics, Money } from "./kpi";
import { future } from "./alerts";

export interface CategoryRow {
  category: string;
  items: number;
  forecastUnits: number;
  revenue: Money;
  wasteCost: Money;
  /** Waste cost divided by cost of the forecast demand; currency-free, comparable. */
  wasteRate: number | null;
}

/** Forecast and waste per product group (7-day outlook, open days only). */
export function byCategory(
  metrics: ItemMetrics[],
  fallback: string,
  costShare: number = COST_SHARE,
): CategoryRow[] {
  const map = new Map<string, CategoryRow & { demandCost: number }>();
  for (const m of metrics) {
    const name = m.item.category || fallback;
    const row = map.get(name) ?? {
      category: name, items: 0, forecastUnits: 0,
      revenue: { EUR: 0, CHF: 0 }, wasteCost: { EUR: 0, CHF: 0 },
      wasteRate: null, demandCost: 0,
    };
    const units = future(m.item).filter((p) => p.is_open).reduce((s, p) => s + p.point, 0);
    row.items += 1;
    row.forecastUnits += units;
    row.revenue[m.item.currency] += units * m.item.unit_price;
    row.wasteCost[m.item.currency] += m.wasteCost;
    row.demandCost += units * m.item.unit_price * costShare;
    map.set(name, row);
  }
  return [...map.values()]
    .map(({ demandCost, ...r }) => ({
      ...r,
      wasteRate: demandCost > 0 ? (r.wasteCost.EUR + r.wasteCost.CHF) / demandCost : null,
    }))
    .sort((a, b) => b.forecastUnits - a.forecastUnits);
}
