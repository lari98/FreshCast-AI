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

/** Raw sums for one market x chain x policy; ratios are recomputed after filtering. */
export interface SegmentSums {
  received: number;
  demand: number;
  sold: number;
  lost: number;
  waste: number;
  revenue: number;
  waste_cost: number;
  lost_margin: number;
  profit: number;
}

export interface Segment {
  market: string;
  chain: string;
  currency: string;
  policies: Partial<Record<PolicyId, SegmentSums>>;
}

export interface Replay {
  disclaimer: string;
  from: string;
  to: string;
  series: number;
  policies: Record<PolicyId, Record<string, PolicyStats>>;
  /** Per market (country prefix of the store id); optional in older files. */
  markets?: Record<string, { currency: string; policies: Record<PolicyId, Omit<PolicyStats, "revenue" | "waste_units" | "lost_units">> }>;
  /** Market x chain sums (newer files); the UI aggregates them for the active filter. */
  segments?: Segment[];
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

export interface Block {
  market: string;
  currency: string;
  chains: string[];
  stats: Partial<Record<PolicyId, PolicyStats>>;
}

const ZERO: SegmentSums = {
  received: 0, demand: 0, sold: 0, lost: 0, waste: 0, revenue: 0, waste_cost: 0, lost_margin: 0, profit: 0,
};

/**
 * Add up the segments of every selected market and chain and rebuild the ratios
 * from the sums (a ratio of ratios would be wrong). One block per market.
 */
export function aggregateSegments(
  segments: Segment[],
  markets: ReadonlySet<string> | null,
  chains: ReadonlySet<string> | null,
  currencies: ReadonlySet<string> | null,
): Block[] {
  const picked = segments.filter(
    (s) =>
      (!markets || markets.has(s.market)) &&
      (!chains || !s.chain || chains.has(s.chain)) &&
      (!currencies || currencies.has(s.currency)),
  );
  const byMarket = new Map<string, Segment[]>();
  for (const s of picked) byMarket.set(s.market, [...(byMarket.get(s.market) ?? []), s]);
  const order = ["DE", "AT", "CH"];
  return [...byMarket.entries()]
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([market, segs]) => {
      const sums = {} as Record<PolicyId, SegmentSums>;
      for (const p of POLICY_IDS) {
        sums[p] = segs.reduce<SegmentSums>((acc, s) => {
          const v = s.policies[p] ?? ZERO;
          return {
            received: acc.received + v.received, demand: acc.demand + v.demand, sold: acc.sold + v.sold,
            lost: acc.lost + v.lost, waste: acc.waste + v.waste, revenue: acc.revenue + v.revenue,
            waste_cost: acc.waste_cost + v.waste_cost, lost_margin: acc.lost_margin + v.lost_margin,
            profit: acc.profit + v.profit,
          };
        }, ZERO);
      }
      const stats: Partial<Record<PolicyId, PolicyStats>> = {};
      for (const p of POLICY_IDS) {
        const v = sums[p];
        const base = sums.naive.profit;
        const baseWaste = sums.naive.waste_cost;
        stats[p] = {
          revenue: v.revenue, profit: v.profit, waste_cost: v.waste_cost, lost_margin: v.lost_margin,
          waste_units: v.waste, lost_units: v.lost,
          fill_rate: v.demand > 0 ? v.sold / v.demand : 0,
          waste_rate: v.received > 0 ? v.waste / v.received : 0,
          profit_vs_naive: base !== 0 ? v.profit / base - 1 : null,
          waste_cost_vs_naive: baseWaste !== 0 ? v.waste_cost / baseWaste - 1 : null,
        };
      }
      return {
        market,
        currency: segs[0]!.currency,
        chains: [...new Set(segs.map((s) => s.chain).filter(Boolean))].sort(),
        stats,
      };
    });
}
