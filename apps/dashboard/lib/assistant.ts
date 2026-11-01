import { attentionList } from "./kpi";
import type { ItemMetrics } from "./kpi";
import { buildAlerts } from "./alerts";

export type QuestionId = "attention" | "order" | "expiry" | "stockout" | "waste";

export interface Answer {
  id: QuestionId;
  /** Items behind the answer, so every statement can be checked in the tabs. */
  lines: { key: string; value: number; currency: "EUR" | "CHF" | "units" }[];
}

/** Keywords (lower case, DE + EN) that route a free-text question to one of the fixed answers. */
const KEYWORDS: Record<QuestionId, string[]> = {
  attention: ["attention", "aufmerksamkeit", "wichtig", "priority", "priorit", "problem"],
  order: ["order", "bestell", "nachbestell", "reorder"],
  expiry: ["expir", "verfall", "ablauf", "mhd", "haltbar", "use-by"],
  stockout: ["stock", "ausverkauf", "leer", "out of", "fehlmenge", "knapp"],
  waste: ["waste", "ausschuss", "verderb", "wegwerf"],
};

export function route(question: string): QuestionId | null {
  const q = question.toLowerCase();
  for (const id of Object.keys(KEYWORDS) as QuestionId[]) {
    if (KEYWORDS[id].some((k) => q.includes(k))) return id;
  }
  return null;
}

/**
 * Deterministic answers computed from the loaded data. This is NOT a language
 * model: it cannot invent numbers. In the target architecture a Bedrock model
 * phrases the answer, and a guard rejects any number that is not in these lines.
 */
export function answer(id: QuestionId, metrics: ItemMetrics[], limit = 5): Answer {
  const items = metrics.map((m) => m.item);
  const cur = (m: ItemMetrics) => m.item.currency;
  switch (id) {
    case "attention":
      return {
        id,
        lines: attentionList(metrics, limit).map((m) => ({
          key: m.key, value: m.attention + m.atRiskCost, currency: cur(m),
        })),
      };
    case "order":
      return {
        id,
        lines: metrics
          .filter((m) => m.orderUnits > 0)
          .sort((a, b) => b.orderCost - a.orderCost)
          .slice(0, limit)
          .map((m) => ({ key: m.key, value: m.orderUnits, currency: "units" as const })),
      };
    case "expiry":
      return {
        id,
        lines: metrics
          .filter((m) => m.atRiskCost > 0)
          .sort((a, b) => b.atRiskCost - a.atRiskCost)
          .slice(0, limit)
          .map((m) => ({ key: m.key, value: m.atRiskCost, currency: cur(m) })),
      };
    case "stockout":
      return {
        id,
        lines: buildAlerts(items)
          .filter((a) => a.kind === "stockout")
          .slice(0, limit)
          .map((a) => ({ key: a.key, value: a.value, currency: "units" as const })),
      };
    case "waste":
      return {
        id,
        lines: [...metrics]
          .filter((m) => m.wasteCost > 0)
          .sort((a, b) => b.wasteCost - a.wasteCost)
          .slice(0, limit)
          .map((m) => ({ key: m.key, value: m.wasteCost, currency: cur(m) })),
      };
  }
}
