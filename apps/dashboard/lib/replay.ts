/** Shape of public/demo/replay.json, written by `python -m freshcast.replenishment.replay`. */

export const POLICY_IDS = ["naive", "rule_v1", "newsvendor", "planner"] as const;
export type PolicyId = (typeof POLICY_IDS)[number];

export interface PolicyStats {
  revenue: number;
  profit: number;
  waste_cost: number;
  lost_margin: number;
  waste_units: number;
  lost_units: number;
  fill_rate: number;
  waste_rate: number;
  profit_vs_naive: number | null;
  waste_cost_vs_naive: number | null;
}

export interface Replay {
  disclaimer: string;
  from: string;
  to: string;
  series: number;
  policies: Record<PolicyId, Record<string, PolicyStats>>;
  weekly: Record<PolicyId, { waste: number[]; lost: number[] }>;
  categories: Record<string, Partial<Record<PolicyId, { waste_rate: number; fill_rate: number }>>>;
  newsvendor_beats_rule_v1_weeks: { wins: number; weeks: number };
  overage_factors: Record<string, number>;
}

export async function loadReplay(fetchImpl: typeof fetch = fetch): Promise<Replay> {
  const response = await fetchImpl("/demo/replay.json", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Replay request failed with status ${response.status}`);
  return validateReplay(await response.json());
}

export function validateReplay(payload: unknown): Replay {
  const r = payload as Partial<Replay> | null;
  if (!r || typeof r.from !== "string" || !r.policies || !r.weekly) {
    throw new Error("Unexpected replay format");
  }
  return r as Replay;
}

/** Relative change of ``a`` against ``b`` (e.g. -0.37 = 37 % lower), null if b is 0. */
export function change(a: number, b: number): number | null {
  return b === 0 ? null : a / b - 1;
}
