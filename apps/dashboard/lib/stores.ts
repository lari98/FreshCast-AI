import { buildAlerts } from "./alerts";
import { pooledAccuracy } from "./accuracy";
import type { Accuracy } from "./accuracy";
import type { ItemMetrics } from "./kpi";

export interface StoreRow {
  storeId: string;
  city: string;
  currency: "EUR" | "CHF";
  items: number;
  itemsToOrder: number;
  orderCost: number;
  wasteCost: number;
  lostMargin: number;
  atRiskCost: number;
  alerts: number;
  accuracy: Accuracy;
  /** Waste + lost margin divided by order cost; comparable across stores and currencies. */
  lossRatio: number | null;
}

export function byStore(metrics: ItemMetrics[]): StoreRow[] {
  const ids = [...new Set(metrics.map((m) => m.item.store_id))];
  return ids.map((id) => {
    const ms = metrics.filter((m) => m.item.store_id === id);
    const sum = (f: (m: ItemMetrics) => number) => ms.reduce((s, m) => s + f(m), 0);
    const orderCost = sum((m) => m.orderCost);
    const loss = sum((m) => m.wasteCost + m.lostMargin);
    return {
      storeId: id,
      city: ms[0]!.item.city,
      currency: ms[0]!.item.currency,
      items: ms.length,
      itemsToOrder: ms.filter((m) => m.orderUnits > 0).length,
      orderCost,
      wasteCost: sum((m) => m.wasteCost),
      lostMargin: sum((m) => m.lostMargin),
      atRiskCost: sum((m) => m.atRiskCost),
      alerts: buildAlerts(ms.map((m) => m.item)).length,
      accuracy: pooledAccuracy(ms.map((m) => m.item.series)),
      lossRatio: orderCost > 0 ? loss / orderCost : null,
    };
  });
}
