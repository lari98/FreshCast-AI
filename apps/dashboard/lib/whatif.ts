import type { Proposal } from "./types";

export interface Scenario {
  /** Relative change of the forecast demand, e.g. 0.2 = +20 %. */
  demandChange: number;
  /** Multiplier on the safety stock, 1 = unchanged. */
  safetyFactor: number;
}

export const NEUTRAL: Scenario = { demandChange: 0, safetyFactor: 1 };

/**
 * The target-stock rule used by the backend baseline:
 * target = forecast + safety stock; order = shortage rounded up to full packs.
 * The planner recommendation additionally weighs expiry, cost and lost sales,
 * so it is shown next to this rule, not replaced by it.
 */
export function ruleOrder(p: Proposal, s: Scenario = NEUTRAL): number {
  const target = p.forecast_units * (1 + s.demandChange) + p.safety_stock_units * s.safetyFactor;
  const shortage = Math.max(0, Math.ceil(target - p.usable_stock_units - 1e-9));
  return Math.ceil(shortage / p.order_multiple) * p.order_multiple;
}
