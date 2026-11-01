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
    expect(t.items).toBe(24);
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
