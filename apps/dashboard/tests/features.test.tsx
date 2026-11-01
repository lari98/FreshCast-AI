import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { Dashboard } from "@/components/Dashboard";
import { buildAlerts } from "@/lib/alerts";
import { answer, route } from "@/lib/assistant";
import { byCategory } from "@/lib/categories";
import { itemMetrics } from "@/lib/kpi";
import type { DashboardData } from "@/lib/types";

const data = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8"),
) as DashboardData;
const metrics = data.items.map(itemMetrics);

beforeEach(() => window.history.replaceState(null, "", "#"));

describe("alerts", () => {
  it("every alert is explained by a number and expiry alerts match the lots", () => {
    const alerts = buildAlerts(data.items);
    for (const a of alerts) expect(Number.isFinite(a.value)).toBe(true);
    for (const a of alerts.filter((x) => x.kind === "expiry")) {
      const units = a.item.lots.filter((l) => l.days_left <= 1).reduce((s, l) => s + l.quantity, 0);
      expect(a.value).toBe(units);
    }
  });
});

describe("assistant", () => {
  it("routes German and English keywords and rejects the rest", () => {
    expect(route("Was muss ich bestellen?")).toBe("order");
    expect(route("what expires soon")).toBe("expiry");
    expect(route("tell me a joke")).toBeNull();
  });
  it("only returns items that exist in the data", () => {
    const keys = new Set(metrics.map((m) => m.key));
    for (const id of ["attention", "order", "expiry", "stockout", "waste"] as const) {
      for (const l of answer(id, metrics).lines) expect(keys.has(l.key)).toBe(true);
    }
  });
});

describe("categories", () => {
  it("conserves the forecast units", () => {
    const rows = byCategory(metrics, "x");
    const sum = rows.reduce((s, r) => s + r.forecastUnits, 0);
    const direct = data.items.reduce(
      (s, i) => s + i.series.filter((p) => p.actual === null && p.is_open).reduce((a, p) => a + p.point, 0), 0);
    expect(sum).toBeCloseTo(direct, 6);
  });
});

describe("new tabs", () => {
  it("assistant answers a chip question", async () => {
    window.history.replaceState(null, "", "#assistant");
    render(<Dashboard load={async () => data} />);
    await userEvent.click(await screen.findByRole("button", { name: "Was muss ich bestellen?" }));
    expect(await screen.findByText(/größten Bestellwert/)).toBeInTheDocument();
  });
  it("assistant refuses unknown questions", async () => {
    window.history.replaceState(null, "", "#assistant");
    render(<Dashboard load={async () => data} />);
    await userEvent.type(await screen.findByRole("textbox"), "tell me a joke{Enter}");
    expect(await screen.findByText(/nicht beantworten/)).toBeInTheDocument();
  });
  it("plan, alerts and categories render tables", async () => {
    for (const h of ["plan", "alerts", "categories"]) {
      window.history.replaceState(null, "", `#${h}`);
      const { unmount } = render(<Dashboard load={async () => data} />);
      expect((await screen.findAllByRole("table")).length).toBeGreaterThan(0);
      unmount();
    }
  });
});
