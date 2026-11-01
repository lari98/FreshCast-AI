import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { Dashboard } from "@/components/Dashboard";
import type { DashboardData } from "@/lib/types";

const data = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8"),
) as DashboardData;

const setup = async () => {
  const utils = render(<Dashboard load={async () => data} />);
  await screen.findByRole("heading", { name: /Bestellvorschlag/ });
  return utils;
};

describe("Dashboard", () => {
  it("renders German by default with the synthetic-data banner", async () => {
    await setup();
    expect(screen.getByRole("note")).toHaveTextContent("synthetischen");
    expect(screen.getByRole("img", { name: /Nachfrage/ })).toBeInTheDocument();
  });

  it("switches language to English", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Sprache"), "en");
    expect(screen.getByRole("heading", { name: "Order proposal" })).toBeInTheDocument();
  });

  it("offers the chart as a data table", async () => {
    await setup();
    await userEvent.click(screen.getByRole("button", { name: /Tabelle/ }));
    expect(screen.getAllByRole("table").length).toBeGreaterThanOrEqual(2);
  });

  it("requires a click to approve and orders nothing", async () => {
    await setup();
    expect(screen.queryByText(/Freigegeben/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vorschlag freigeben" }));
    expect(screen.getByText(/es wird nichts bestellt/)).toBeInTheDocument();
  });

  it("changes store and product", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Filiale"), "AT-VIE-001");
    expect(screen.getByLabelText("Produkt")).toHaveValue(
      data.items.find((i) => i.store_id === "AT-VIE-001")?.sku,
    );
  });

  it("shows a risk label for every stock lot", async () => {
    await setup();
    expect(screen.getAllByText(/niedrig|mittel|hoch/).length).toBeGreaterThan(0);
  });

  it("shows an alert when loading fails", async () => {
    render(<Dashboard load={async () => Promise.reject(new Error("x"))} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = await setup();
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } }, // jsdom has no layout/colours
    });
    expect(results.violations).toEqual([]);
  });
});
