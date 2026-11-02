import { buildAlerts, future } from "./alerts";
import type { ItemMetrics } from "./kpi";
import { marketOf } from "./markets";
import type { Item } from "./types";
import type { Role, Workflow } from "./workflow";

export type TaskId = "approve" | "review" | "expiry" | "stockout" | "spike" | "closures";

export interface Task {
  id: TaskId;
  /** Tab that helps to do it. */
  tab: string;
  count: number;
}

export interface Closure {
  date: string;
  /** Stores that are closed on that day (every item of the store has no trading). */
  stores: { id: string; city: string; market: string }[];
}

/** Days on which a whole store does not trade, from the forecast calendar. */
export function closures(items: Item[], horizon = 7): Closure[] {
  const byStore = new Map<string, Item[]>();
  for (const item of items) byStore.set(item.store_id, [...(byStore.get(item.store_id) ?? []), item]);
  const byDate = new Map<string, Closure["stores"]>();
  for (const [id, list] of byStore) {
    const days = new Map<string, boolean[]>();
    for (const item of list) {
      for (const p of future(item).slice(0, horizon)) days.set(p.date, [...(days.get(p.date) ?? []), p.is_open]);
    }
    for (const [date, flags] of days) {
      if (flags.length > 0 && flags.every((open) => !open)) {
        byDate.set(date, [...(byDate.get(date) ?? []), { id, city: list[0]!.city, market: marketOf(list[0]!) }]);
      }
    }
  }
  return [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, stores]) => ({ date, stores }));
}

/** What needs attention today, with the counts behind each line. Zero-count lines are dropped. */
export function buildTasks(
  metrics: ItemMetrics[], items: Item[], workflow: Workflow, role: Role, asOf: string,
): Task[] {
  const alerts = buildAlerts(items);
  const state = (key: string) => workflow[key]?.status ?? "draft";
  const toSubmit = metrics.filter((m) => m.orderUnits > 0 && ["draft", "rejected"].includes(state(m.key))).length;
  const toReview = metrics.filter((m) => state(m.key) === "submitted").length;
  const soon = new Date(`${asOf}T00:00:00Z`).getTime() + 3 * 86_400_000;
  const nearClosures = closures(items).filter((c) => new Date(`${c.date}T00:00:00Z`).getTime() < soon).length;
  const all: Task[] = [
    role === "reviewer"
      ? { id: "review", tab: "approval", count: toReview }
      : { id: "approve", tab: "approval", count: toSubmit },
    { id: "expiry", tab: "expiry", count: metrics.filter((m) => m.atRiskCost > 0).length },
    { id: "stockout", tab: "alerts", count: alerts.filter((a) => a.kind === "stockout").length },
    { id: "spike", tab: "alerts", count: alerts.filter((a) => a.kind === "spike" || a.kind === "drop").length },
    { id: "closures", tab: "plan", count: nearClosures },
  ];
  return all.filter((task) => task.count > 0);
}
