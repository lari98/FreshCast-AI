/** Tab ids, in display order inside their groups (see Dashboard for the labels). */
export const TAB_IDS = [
  "today", "overview", "map", "stores", "alerts", "orders", "approval", "whatif", "forecast", "plan", "categories",
  "expiry", "markdown", "savings", "assistant", "model", "data", "settings", "help",
] as const;
export type TabId = (typeof TAB_IDS)[number];

export function tabFromHash(hash: string): TabId {
  const h = hash.replace("#", "");
  return (TAB_IDS as readonly string[]).includes(h) ? (h as TabId) : "today";
}
