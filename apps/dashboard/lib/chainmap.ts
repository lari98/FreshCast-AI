import { chainOf, marketOf } from "./markets";
import type { ItemMetrics } from "./kpi";

export interface MapCell {
  stores: number;
  items: number;
  /** Waste + lost margin divided by order cost (null when nothing is ordered). */
  lossRatio: number | null;
}

export interface MapRow {
  chain: string;
  /** Markets where the chain has at least one store, in the order of `markets`. */
  countries: string[];
  cells: Record<string, MapCell | undefined>;
}

export interface ChainMap {
  markets: string[];
  rows: MapRow[];
}

/**
 * Chain x market matrix of the whole network. A chain that sells in several
 * countries (a discounter, say) shows one cell per country, so the same banner
 * can be compared across markets.
 */
export function chainMap(metrics: ItemMetrics[], markets: string[]): ChainMap {
  const chains = [...new Set(metrics.map((m) => chainOf(m.item)).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
  const rows = chains.map<MapRow>((chain) => {
    const cells: Record<string, MapCell | undefined> = {};
    for (const market of markets) {
      const ms = metrics.filter((m) => chainOf(m.item) === chain && marketOf(m.item) === market);
      if (ms.length === 0) continue;
      const order = ms.reduce((s, m) => s + m.orderCost, 0);
      const loss = ms.reduce((s, m) => s + m.wasteCost + m.lostMargin, 0);
      cells[market] = {
        stores: new Set(ms.map((m) => m.item.store_id)).size,
        items: ms.length,
        lossRatio: order > 0 ? loss / order : null,
      };
    }
    return { chain, countries: markets.filter((m) => cells[m]), cells };
  });
  return { markets, rows };
}
