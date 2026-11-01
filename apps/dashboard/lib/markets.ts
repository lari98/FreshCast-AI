import type { Item } from "./types";

export type Currency = Item["currency"];
export const CURRENCIES: Currency[] = ["EUR", "CHF"];
const KNOWN = ["DE", "AT", "CH"] as const;
export const OTHER = "OTHER";

/** Market of an item: the country prefix of the store id (DE-MUC-001 -> DE). */
export function marketOf(item: Pick<Item, "store_id">): string {
  const prefix = item.store_id.split("-")[0]?.toUpperCase() ?? "";
  return (KNOWN as readonly string[]).includes(prefix) ? prefix : OTHER;
}

/** Markets that exist in the data, in a stable order (DE, AT, CH, other). */
export function availableMarkets(items: Item[]): string[] {
  const present = new Set(items.map(marketOf));
  return [...KNOWN, OTHER].filter((m) => present.has(m));
}

export function availableCurrencies(items: Item[]): Currency[] {
  const present = new Set(items.map((i) => i.currency));
  return CURRENCIES.filter((c) => present.has(c));
}

/** Items that belong to a selected market AND have a selected currency. */
export function filterMarkets(
  items: Item[],
  markets: ReadonlySet<string> | null,
  currencies: ReadonlySet<string> | null,
): Item[] {
  return items.filter(
    (i) => (!markets || markets.has(marketOf(i))) && (!currencies || currencies.has(i.currency)),
  );
}

export interface Preset {
  id: string;
  markets: string[];
}

/** Quick choices for the header. "all" means no restriction. */
export const PRESETS: Preset[] = [
  { id: "all", markets: ["DE", "AT", "CH", OTHER] },
  { id: "DE", markets: ["DE"] },
  { id: "AT", markets: ["AT"] },
  { id: "CH", markets: ["CH"] },
  { id: "DE+AT", markets: ["DE", "AT"] },
];

/** Which preset the current selection equals (ignoring markets not in the data). */
export function presetFor(selected: ReadonlySet<string>, available: string[]): string {
  const key = (xs: Iterable<string>) => [...new Set(xs)].filter((m) => available.includes(m)).sort().join(",");
  const current = key(selected);
  for (const p of PRESETS) if (key(p.markets) === current) return p.id;
  return "custom";
}
