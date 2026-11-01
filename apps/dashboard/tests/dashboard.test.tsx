import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { beforeEach, describe, expect, it } from "vitest";
import { Dashboard } from "@/components/Dashboard";
import { csvCell } from "@/components/OrdersTab";
import { STRINGS } from "@/lib/i18n";
import type { Replay } from "@/lib/replay";
import type { DashboardData } from "@/lib/types";

const data = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8"),
) as DashboardData;

const replay = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/replay.json"), "utf-8"),
) as Replay;

const setup = async () => {
  const utils = render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
  await screen.findByRole("tablist");
  return utils;
};
const openTab = (name: RegExp) => userEvent.click(screen.getByRole("tab", { name }));

beforeEach(() => {
  window.history.replaceState(null, "", "#");
});

describe("Dashboard shell", () => {
  it("opens on the overview with the synthetic-data banner and KPI cards", async () => {
    await setup();
    expect(screen.getByRole("note")).toHaveTextContent("synthetischen");
    expect(screen.getByRole("tab", { name: "Übersicht" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Erwarteter Ausschuss")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Das braucht Aufmerksamkeit" })).toBeInTheDocument();
  });

  it("switches language to English", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Sprache"), "en");
    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
  });

  it("moves between tabs with the arrow keys", async () => {
    await setup();
    screen.getByRole("tab", { name: "Übersicht" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Bestellungen" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Modell" })).toHaveAttribute("aria-selected", "true");
  });

  it("keeps the tab in the URL hash", async () => {
    await setup();
    await openTab(/Verfall/);
    expect(window.location.hash).toBe("#expiry");
  });

  it("narrows every tab to one store", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Bereich"), data.items[0]!.store_id);
    await openTab(/Bestellungen/);
    const rows = within(screen.getByRole("table")).getAllByRole("row").length - 1;
    expect(rows).toBe(data.items.filter((i) => i.store_id === data.items[0]!.store_id).length);
  });

  it("shows an alert when loading fails", async () => {
    render(<Dashboard load={async () => Promise.reject(new Error("x"))} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});

describe("Tabs", () => {
  it("orders: filters, approves a selection and counts it for export", async () => {
    await setup();
    await openTab(/Bestellungen/);
    const first = screen.getAllByRole("checkbox", { name: /Zeile auswählen/ })[0]!;
    await userEvent.click(first);
    await userEvent.click(screen.getByRole("button", { name: /Auswahl freigeben/ }));
    expect(screen.getAllByText(/freigegeben/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /CSV/ })).toBeEnabled();
    await userEvent.type(screen.getByRole("searchbox"), "zzzz-none");
    expect(screen.getByText(STRINGS.de.noItems)).toBeInTheDocument();
  });

  it("forecast: shows chart, proposal and accuracy; approval needs a click", async () => {
    await setup();
    await openTab(/Prognose/);
    expect(screen.getByRole("img", { name: /Nachfrage/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prognosegüte der letzten Tage (nicht im Training)" })).toBeInTheDocument();
    expect(screen.queryByText(/es wird nichts bestellt/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vorschlag freigeben" }));
    expect(screen.getByText(/es wird nichts bestellt/)).toBeInTheDocument();
  });

  it("expiry: labels the markdown hint as a rule, not an AI decision", async () => {
    await setup();
    await openTab(/Verfall/);
    expect(screen.getByText(/keine KI-Entscheidung/)).toBeInTheDocument();
    expect(screen.getAllByText(/niedrig|mittel|hoch/).length).toBeGreaterThan(0);
  });

  it("what-if: a demand increase never lowers the rule quantity", async () => {
    await setup();
    await openTab(/Was-wäre-wenn|What-if/);
    const dd = screen.getByText("Regelbasierte Menge").closest("div")!;
    const before = Number(dd.textContent!.replace(/\D+/g, " ").trim().split(" ")[0]);
    const slider = screen.getByRole("slider", { name: /Nachfrageänderung/ });
    slider.focus();
    await userEvent.keyboard("{ArrowRight}".repeat(8));
    const after = Number(screen.getByText("Regelbasierte Menge").closest("div")!.textContent!.replace(/\D+/g, " ").trim().split(" ")[0]);
    expect(after).toBeGreaterThanOrEqual(before);
  });

  it("savings: shows the policies, the paired-week check and the synthetic-data notice", async () => {
    await setup();
    await openTab(/Einsparungen/);
    expect(screen.getByText(/Synthetische Daten und angenommene Kosten/)).toBeInTheDocument();
    expect(screen.getAllByText("Newsvendor (kostenoptimal)", { selector: "th" }).length).toBeGreaterThan(0);
    const { wins, weeks } = replay.newsvendor_beats_rule_v1_weeks;
    expect(screen.getByText(new RegExp(`${wins} von ${weeks}`))).toBeInTheDocument();
  });

  it("savings: reports an error when the replay file is missing", async () => {
    window.history.replaceState(null, "", "#savings");
    render(<Dashboard load={async () => data} loadReplay={async () => Promise.reject(new Error("x"))} />);
    expect(await screen.findByText(/Replay-Daten konnten nicht geladen/)).toBeInTheDocument();
  });

  it("model: states the numbers are synthetic", async () => {
    await setup();
    await openTab(/Modell/);
    expect(screen.getByRole("heading", { name: /Prognosegüte im Rückblick \(synthetische/ })).toBeInTheDocument();
    expect(screen.getByText(/Keine Zertifizierung/)).toBeInTheDocument();
  });
});

describe("csvCell", () => {
  it("neutralises spreadsheet formulas and quotes separators", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("a;b")).toBe('"a;b"');
    expect(csvCell(5)).toBe("5");
  });
});

describe("accessibility", () => {
  it.each([/Übersicht/, /Bestellungen/, /Prognose/, /Wochenplan/, /Warnungen/, /KI-Assistent/, /Warengruppen/, /Verfall/, /Was-wäre-wenn|What-if/, /Einsparungen/, /Daten/, /Modell/])(
    "has no detectable violations on tab %s",
    async (name) => {
      const { container } = await setup();
      await openTab(name);
      const results = await axe.run(container, {
        rules: { "color-contrast": { enabled: false } }, // jsdom has no layout/colours
      });
      expect(results.violations).toEqual([]);
    },
  );
});
