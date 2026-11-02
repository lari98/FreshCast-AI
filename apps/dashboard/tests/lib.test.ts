import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { accuracy } from "@/lib/accuracy";
import { attentionList, itemMetrics, totals } from "@/lib/kpi";
import type { DashboardData } from "@/lib/types";
import { NEUTRAL, ruleOrder } from "@/lib/whatif";

const data = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8"),
) as DashboardData;

describe("accuracy", () => {
  const pt = (actual: number | null, point: number, lower: number, upper: number) => ({
    date: "2025-01-01", actual, point, lower, upper, is_open: true,
  });
  it("computes WAPE, bias and coverage over days with actuals", () => {
    const a = accuracy([pt(10, 12, 8, 14), pt(20, 18, 15, 19), pt(null, 5, 1, 9)]);
    expect(a.days).toBe(2);
    expect(a.wape).toBeCloseTo(4 / 30);
    expect(a.bias).toBeCloseTo(0); // +2 and -2 cancel
    expect(a.coverage).toBeCloseTo(0.5); // 20 is outside [15, 19]
  });
  it("returns nulls without usable days", () => {
    expect(accuracy([pt(null, 1, 0, 2)]).wape).toBeNull();
    expect(accuracy([pt(0, 1, 0, 2)]).wape).toBeNull();
  });
  it("ignores closed days", () => {
    const closed = { ...pt(0, 0, 0, 0), is_open: false };
    expect(accuracy([closed, pt(10, 10, 9, 11)]).days).toBe(1);
  });
});

describe("kpi", () => {
  const metrics = data.items.map(itemMetrics);
  it("computes value from units, price and the stated cost share", () => {
    const m = metrics[0]!;
    expect(m.orderCost).toBeCloseTo(m.orderUnits * m.item.unit_price * 0.6);
  });
  it("sums per currency without mixing EUR and CHF", () => {
    const t = totals(metrics);
    const eur = metrics.filter((m) => m.item.currency === "EUR").reduce((s, m) => s + m.orderCost, 0);
    expect(t.orderCost.EUR).toBeCloseTo(eur);
    expect(t.orderCost.CHF).toBeGreaterThan(0);
    expect(t.items).toBe(56);
  });
  it("ranks the attention list by value, highest first", () => {
    const list = attentionList(metrics, 5);
    const score = (m: (typeof list)[number]) => m.attention + m.atRiskCost;
    expect(list.length).toBeLessThanOrEqual(5);
    for (let i = 1; i < list.length; i++) {
      expect(score(list[i - 1]!)).toBeGreaterThanOrEqual(score(list[i]!));
    }
  });
});

describe("what-if rule", () => {
  const p = { ...data.items[0]!.proposal, forecast_units: 100, safety_stock_units: 20, usable_stock_units: 30, order_multiple: 12 };
  it("rounds the shortage up to full packs", () => {
    expect(ruleOrder(p, NEUTRAL)).toBe(96); // target 120, shortage 90 -> 8 packs
  });
  it("reacts to demand and safety changes", () => {
    expect(ruleOrder(p, { demandChange: 0.2, safetyFactor: 1 })).toBe(120); // 140-30=110 -> 10 packs
    expect(ruleOrder(p, { demandChange: 0, safetyFactor: 0 })).toBe(72); // 70 -> 6 packs
  });
  it("never orders a negative amount", () => {
    expect(ruleOrder({ ...p, usable_stock_units: 500 })).toBe(0);
  });
});

import { change, validateReplay } from "@/lib/replay";

describe("replay helpers", () => {
  it("computes relative change and guards a zero base", () => {
    expect(change(63, 100)).toBeCloseTo(-0.37);
    expect(change(5, 0)).toBeNull();
  });
  it("rejects a payload with the wrong shape", () => {
    expect(() => validateReplay({})).toThrow();
  });
});

import { byStore } from "@/lib/stores";
import { bestMarkdown, lotExcess, markdownOutcome } from "@/lib/markdown";
import { canSubmit, decide, parseWorkflow, setQuantity, setReason, submit } from "@/lib/workflow";

describe("workflow (four eyes)", () => {
  const lookup = () => ({ proposed: 12, packSize: 6 });
  it("rounds a changed quantity to whole packs and needs a reason to submit", () => {
    let wf = setQuantity({}, "a", 12, 6, 17);
    expect(wf.a!.qty).toBe(18);
    expect(canSubmit(wf.a!)).toBe(false);
    wf = setReason(wf, "a", "promo");
    expect(canSubmit(wf.a!)).toBe(true);
    wf = submit(wf, ["a"], lookup);
    expect(wf.a!.status).toBe("submitted");
  });
  it("only a reviewer can approve, and only submitted orders", () => {
    let wf = submit({}, ["a"], lookup);
    expect(decide(wf, ["a"], "planner", true).a!.status).toBe("submitted");
    wf = decide(wf, ["a"], "reviewer", true);
    expect(wf.a!.status).toBe("approved");
    expect(decide({}, ["b"], "reviewer", true)).toEqual({});
  });
  it("changing an approved quantity sends it back to draft", () => {
    let wf = decide(submit({}, ["a"], lookup), ["a"], "reviewer", true);
    wf = setQuantity(wf, "a", 12, 6, 6);
    expect(wf.a!.status).toBe("draft");
  });
  it("parses stored data defensively", () => {
    expect(parseWorkflow("junk")).toEqual({});
    expect(parseWorkflow({ a: { proposed: 1, qty: 1, packSize: 0, status: "draft" } })).toEqual({});
    expect(Object.keys(parseWorkflow({ a: { proposed: 6, qty: 6, packSize: 6, status: "approved" } }))).toEqual(["a"]);
  });
});

describe("markdown what-if", () => {
  const metrics = data.items.map(itemMetrics);
  it("never reports excess above the lot quantity", () => {
    for (const item of data.items) {
      for (const row of lotExcess(item)) {
        expect(row.excess).toBeGreaterThanOrEqual(0);
        expect(row.excess).toBeLessThanOrEqual(row.quantity);
      }
    }
  });
  it("a deeper cut at zero elasticity never helps", () => {
    const item = data.items[0]!;
    expect(markdownOutcome(item.unit_price, lotExcess(item), 0.3, 0).net).toBeLessThanOrEqual(0);
    expect(bestMarkdown(item.unit_price, lotExcess(item), 0)).toBeNull();
  });
  it("store rows sum back to the totals", () => {
    const rows = byStore(metrics);
    expect(rows.reduce((s, r) => s + r.items, 0)).toBe(metrics.length);
  });
});

import { availableChains, availableMarkets, chainOf, filterMarkets, marketOf, presetFor } from "@/lib/markets";
import { chainMap } from "@/lib/chainmap";
import { aggregateSegments } from "@/lib/replay";
import type { Segment } from "@/lib/replay";

describe("markets", () => {
  it("reads the country from the store id", () => {
    expect(marketOf({ store_id: "DE-MUC-001" })).toBe("DE");
    expect(marketOf({ store_id: "ch-zrh-001" })).toBe("CH");
    expect(marketOf({ store_id: "S1" })).toBe("OTHER");
  });
  it("filters by market and currency together", () => {
    expect(availableMarkets(data.items)).toEqual(["DE", "AT", "CH"]);
    const de = filterMarkets(data.items, new Set(["DE"]), null);
    expect(de.length).toBe(24);
    expect(de.every((i) => i.store_id.startsWith("DE-"))).toBe(true);
    expect(filterMarkets(data.items, null, new Set(["CHF"])).every((i) => i.currency === "CHF")).toBe(true);
    expect(filterMarkets(data.items, new Set(["DE"]), new Set(["CHF"]))).toEqual([]);
    expect(filterMarkets(data.items, new Set(), null)).toEqual([]);
  });
  it("recognises presets and custom selections", () => {
    const avail = ["DE", "AT", "CH"];
    expect(presetFor(new Set(avail), avail)).toBe("all");
    expect(presetFor(new Set(["AT"]), avail)).toBe("AT");
    expect(presetFor(new Set(["DE", "AT"]), avail)).toBe("DE+AT");
    expect(presetFor(new Set(["AT", "CH"]), avail)).toBe("custom");
  });
});

describe("retail chains", () => {
  it("lists the chains and filters by them without hiding chain-less items", () => {
    expect(availableChains(data.items)).toEqual(["AlpenFrisch", "MarktHaus", "PreisPunkt"]);
    const pp = filterMarkets(data.items, null, null, new Set(["PreisPunkt"]));
    expect(pp.length).toBeGreaterThan(0);
    expect(pp.every((i) => chainOf(i) === "PreisPunkt")).toBe(true);
    const bare = { ...data.items[0]!, chain: undefined };
    expect(filterMarkets([bare], null, null, new Set(["PreisPunkt"]))).toHaveLength(1);
  });

  it("shows the same chain in several countries on the map", () => {
    const map = chainMap(data.items.map((i) => itemMetrics(i)), ["DE", "AT", "CH"]);
    const pp = map.rows.find((r) => r.chain === "PreisPunkt")!;
    expect(pp.countries).toEqual(["DE", "AT", "CH"]);
    expect(map.rows.find((r) => r.chain === "MarktHaus")!.countries).toEqual(["DE"]);
    expect(map.rows.find((r) => r.chain === "AlpenFrisch")!.countries).toEqual(["AT", "CH"]);
    expect(pp.cells.DE!.stores).toBe(1);
  });

  const seg = (market: string, chain: string, sold: number, demand: number): Segment => {
    const sums = { received: 100, demand, sold, lost: demand - sold, waste: 5, revenue: 10, waste_cost: 2, lost_margin: 1, profit: 8 };
    return { market, chain, currency: "EUR", policies: { naive: sums, rule_v1: { ...sums, profit: 9 } } };
  };
  it("rebuilds ratios from sums, not from ratios", () => {
    const blocks = aggregateSegments([seg("DE", "A", 90, 100), seg("DE", "B", 10, 20)], null, null, null);
    expect(blocks).toHaveLength(1);
    expect(blocks[0]!.stats.naive!.fill_rate).toBeCloseTo(100 / 120);
    expect(blocks[0]!.stats.rule_v1!.profit_vs_naive).toBeCloseTo(18 / 16 - 1);
    expect(blocks[0]!.chains).toEqual(["A", "B"]);
    const onlyB = aggregateSegments([seg("DE", "A", 90, 100), seg("DE", "B", 10, 20)], null, new Set(["B"]), null);
    expect(onlyB[0]!.stats.naive!.fill_rate).toBeCloseTo(0.5);
  });
  it("matches the full replay when everything is selected", () => {
    const replay = JSON.parse(readFileSync(join(__dirname, "../public/demo/replay.json"), "utf-8"));
    const blocks = aggregateSegments(replay.segments, null, null, null);
    const eur = blocks.filter((b) => b.currency === "EUR");
    const profit = eur.reduce((s, b) => s + b.stats.newsvendor!.profit, 0);
    expect(profit).toBeCloseTo(replay.policies.newsvendor.EUR.profit, 0);
    const nv = replay.policies.newsvendor.EUR;
    expect(nv.profit_vs_naive).toBeCloseTo(profit / eur.reduce((s, b) => s + b.stats.naive!.profit, 0) - 1, 3);
  });
});

import { append, diffWorkflow, MAX_EVENTS, parseAudit } from "@/lib/audit";
import { buildTasks, closures } from "@/lib/today";
import { searchEntries } from "@/components/QuickSearch";
import type { Workflow } from "@/lib/workflow";

describe("audit trail", () => {
  const before: Workflow = { a: { proposed: 10, qty: 10, packSize: 1, status: "draft" } };
  const after: Workflow = {
    a: { proposed: 10, qty: 12, packSize: 1, status: "submitted", reason: "promo" },
    b: { proposed: 5, qty: 5, packSize: 1, status: "draft" },
  };
  it("records only real status changes, with the reason", () => {
    const ev = diffWorkflow(before, after, "planner", "2026-01-01T08:00:00Z");
    expect(ev).toEqual([
      { at: "2026-01-01T08:00:00Z", role: "planner", action: "submitted", key: "a", qty: 12, proposed: 10, reason: "promo" },
    ]);
    expect(diffWorkflow(after, after, "planner", "x")).toEqual([]);
  });
  it("keeps newest first and caps the log", () => {
    const many = Array.from({ length: MAX_EVENTS + 20 }, (_, i) => ({ at: String(i), role: "planner" as const, action: "submitted" as const, key: "k", qty: 1, proposed: 1 }));
    const log = append(many.slice(0, MAX_EVENTS), [many[MAX_EVENTS]!]);
    expect(log).toHaveLength(MAX_EVENTS);
    expect(log[0]!.at).toBe(String(MAX_EVENTS));
  });
  it("drops malformed stored events instead of crashing", () => {
    expect(parseAudit("nope")).toEqual([]);
    expect(parseAudit([{ at: 1 }, null, { at: "t", key: "k", qty: 1, proposed: 1, role: "root", action: "approved" }])).toEqual([]);
    expect(parseAudit([{ at: "t", key: "k", qty: 1, proposed: 1, role: "reviewer", action: "approved", reason: "<script>" }])[0]).not.toHaveProperty("reason");
  });
});

describe("today", () => {
  const metrics = data.items.map((i) => itemMetrics(i));
  it("counts what needs doing and follows the role", () => {
    const planner = buildTasks(metrics, data.items, {}, "planner", data.as_of);
    expect(planner.find((t) => t.id === "approve")!.count).toBe(metrics.filter((m) => m.orderUnits > 0).length);
    expect(planner.some((t) => t.id === "review")).toBe(false);
    const reviewer = buildTasks(metrics, data.items, {}, "reviewer", data.as_of);
    expect(reviewer.some((t) => t.id === "approve")).toBe(false);
  });
  it("finds closing days only when every item of a store is closed", () => {
    const item = data.items[0]!;
    const fut = item.series.filter((p) => p.actual === null);
    const shut = { ...item, series: item.series.map((p) => (p === fut[0] ? { ...p, is_open: false } : p)) };
    const twin = { ...item, sku: "OTHER", series: item.series.map((p) => (p === fut[0] ? { ...p, is_open: true } : p)) };
    const day = fut[0]!.date;
    expect(closures([shut, twin]).map((c) => c.date)).not.toContain(day);
    expect(closures([shut]).map((c) => c.date)).toContain(day);
  });
});

describe("quick search ranking", () => {
  const entries = [
    { id: "orders", kind: "tab" as const, label: "Bestellungen" },
    { id: "k|1", kind: "item" as const, label: "Weizenbrot 750 g", sub: "DE-MUC-001" },
    { id: "approval", kind: "tab" as const, label: "Freigabe" },
  ];
  it("matches label and sub text, ignores accents and case, ranks prefix first", () => {
    expect(searchEntries(entries, "BESTELL").map((e) => e.id)).toEqual(["orders"]);
    expect(searchEntries(entries, "muc").map((e) => e.id)).toEqual(["k|1"]);
    expect(searchEntries(entries, "").every((e) => e.kind === "tab")).toBe(true);
    expect(searchEntries(entries, "zzz")).toEqual([]);
  });
});
