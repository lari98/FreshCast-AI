import { accuracy } from "./accuracy";
import { itemKey } from "./kpi";
import type { Item } from "./types";

export type AlertKind = "expiry" | "stockout" | "spike" | "drop" | "accuracy";
export type Severity = "high" | "medium";

export interface Alert {
  id: string;
  key: string;
  item: Item;
  kind: AlertKind;
  severity: Severity;
  /** Number shown next to the alert (units, percent as fraction, ...). */
  value: number;
}

export const future = (item: Item) => item.series.filter((p) => p.actual === null);
export const history = (item: Item) => item.series.filter((p) => p.actual !== null);

const SPIKE = 0.3;
const WAPE_LIMIT = 0.3;

/** Transparent rules, no model: every alert says which number triggered it. */
export function buildAlerts(items: Item[]): Alert[] {
  const out: Alert[] = [];
  for (const item of items) {
    const key = itemKey(item);
    const add = (kind: AlertKind, severity: Severity, value: number) =>
      out.push({ id: `${key}|${kind}`, key, item, kind, severity, value });

    const expiring = item.lots
      .filter((l) => l.days_left <= 1)
      .reduce((s, l) => s + l.quantity, 0);
    if (expiring > 0) add("expiry", "high", expiring);

    const next = future(item).find((p) => p.is_open);
    if (next && item.proposal.usable_stock_units + 1e-9 < next.point) {
      add("stockout", "high", next.point - item.proposal.usable_stock_units);
    }

    const fut = future(item).filter((p) => p.is_open);
    const hist = history(item).filter((p) => p.is_open);
    const futAvg = fut.length ? fut.reduce((s, p) => s + p.point, 0) / fut.length : 0;
    const histAvg = hist.length ? hist.reduce((s, p) => s + (p.actual ?? 0), 0) / hist.length : 0;
    if (histAvg > 0 && fut.length > 0) {
      const change = futAvg / histAvg - 1;
      if (change >= SPIKE) add("spike", "medium", change);
      else if (change <= -SPIKE) add("drop", "medium", change);
    }

    const acc = accuracy(item.series);
    if (acc.wape !== null && acc.wape > WAPE_LIMIT) add("accuracy", "medium", acc.wape);
  }
  return out.sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "high" ? -1 : 1));
}
