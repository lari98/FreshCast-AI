import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const openTab = (name: RegExp) => userEvent.click(screen.getByRole("tab", { name }));
/** Renders the dashboard on its landing tab ("Heute"). */
const landing = async () => {
  const utils = render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
  await screen.findByRole("tablist");
  return utils;
};
/** Renders the dashboard and opens the overview, where most tests start. */
const setup = async () => {
  const utils = await landing();
  await openTab(/^Übersicht$/);
  return utils;
};

beforeEach(() => {
  window.history.replaceState(null, "", "#");
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("Dashboard shell", () => {
  it("opens on Today with the synthetic-data banner, then shows the overview KPI cards", async () => {
    await landing();
    expect(screen.getByRole("note")).toHaveTextContent("synthetischen");
    expect(screen.getByRole("tab", { name: "Heute" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: /Heute zu tun/ })).toBeInTheDocument();
    await openTab(/^Übersicht$/);
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
    expect(screen.getByRole("tab", { name: "Marktkarte" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Hilfe" })).toHaveAttribute("aria-selected", "true");
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
  it("orders: submit a selection, a reviewer approves it, then it can be exported", async () => {
    await setup();
    await openTab(/Bestellungen/);
    const first = screen.getAllByRole("checkbox", { name: /Zeile auswählen/ })[0]!;
    await userEvent.click(first);
    await userEvent.click(screen.getByRole("button", { name: /Auswahl einreichen/ }));
    expect(screen.getAllByText("eingereicht").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /CSV/ })).toBeDisabled();
    await openTab(/^Freigabe$/);
    await userEvent.selectOptions(screen.getByLabelText("Rolle"), "reviewer");
    await userEvent.click(screen.getByRole("button", { name: /Alle eingereichten freigeben/ }));
    await openTab(/Bestellungen/);
    expect(screen.getAllByText(/✓ freigegeben/).length).toBeGreaterThan(0);
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
    await userEvent.click(screen.getByRole("button", { name: "Zur Freigabe einreichen" }));
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

describe("approval, settings and new tabs", () => {
  it("a changed quantity needs a reason; only the reviewer approves", async () => {
    await setup();
    await openTab(/^Freigabe$/);
    const plus = screen.getAllByRole("button", { name: /^Menge:.*\+\d+$/ })[0]!;
    await userEvent.click(plus);
    expect(screen.getByText("Für eine geänderte Menge ist ein Grund nötig.")).toBeInTheDocument();
    const reason = screen.getAllByRole("combobox", { name: /^Grund:/ })[0]!;
    await userEvent.selectOptions(reason, "promo");
    await userEvent.click(screen.getAllByRole("button", { name: "Einreichen" })[0]!);
    // once in the status cell and once in the decision history below
    expect(screen.getAllByText("eingereicht").length).toBe(2);
    expect(screen.getByRole("heading", { name: "Verlauf der Entscheidungen" })).toBeInTheDocument();
    // planner cannot approve
    expect(screen.getByRole("button", { name: /Alle eingereichten freigeben/ })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Rolle"), "reviewer");
    await userEvent.click(screen.getByRole("button", { name: /Alle eingereichten freigeben/ }));
    expect(screen.getByText(/✓ freigegeben/)).toBeInTheDocument();
    const stored = JSON.parse(window.localStorage.getItem("freshcast.settings.v2")!).audit;
    expect(stored.map((e: { action: string }) => e.action)).toEqual(["approved", "submitted"]);
    expect(stored[0].role).toBe("reviewer");
    expect(stored[1].reason).toBe("promo");
  });

  it("settings: cost share changes the KPIs and is stored in the browser", async () => {
    await setup();
    const before = screen.getByText("Bestellwert (Einkauf)").closest("li")!.textContent;
    await openTab(/Einstellungen/);
    const slider = screen.getByRole("slider", { name: /Einkaufskosten/ });
    fireEvent.change(slider, { target: { value: "70" } });
    await openTab(/Übersicht/);
    expect(screen.getByText("Bestellwert (Einkauf)").closest("li")!.textContent).not.toBe(before);
    expect(JSON.parse(window.localStorage.getItem("freshcast.settings.v2")!).costShare).toBeGreaterThan(0.6);
  });

  it("settings: the theme switch sets data-theme", async () => {
    await setup();
    await openTab(/Einstellungen/);
    await userEvent.selectOptions(screen.getByLabelText("Darstellung"), "dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("stores, markdowns and help render", async () => {
    await setup();
    await openTab(/Filialvergleich/);
    expect(screen.getByRole("heading", { name: "Filialen im Vergleich" })).toBeInTheDocument();
    await openTab(/Preisaktionen/);
    expect(screen.getByText(/Annahme-Rechner/)).toBeInTheDocument();
    await openTab(/Hilfe/);
    expect(screen.getByText(/Vier-Augen-Prinzip: Eine zweite Person/)).toBeInTheDocument();
  });
});

describe("market and currency filter", () => {
  const ordersRows = () => within(screen.getByRole("table")).getAllByRole("row").length - 1;

  it("Germany only: every tab shows only German stores and no CHF", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Markt"), "DE");
    expect(screen.getByLabelText("Bereich")).toHaveTextContent("Munich");
    expect(screen.getByLabelText("Bereich")).not.toHaveTextContent("Vienna");
    expect(screen.getByLabelText("Bereich")).not.toHaveTextContent("Zurich");
    expect(screen.getByText("Bestellwert (Einkauf)").closest("li")!.textContent).not.toMatch(/CHF/);
    await openTab(/Bestellungen/);
    expect(ordersRows()).toBe(24);
  });

  it("Switzerland only: CHF only; Germany + Austria: EUR only", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Markt"), "CH");
    const li = screen.getByText("Bestellwert (Einkauf)").closest("li")!;
    expect(li.textContent).toMatch(/CHF/);
    expect(li.textContent).not.toMatch(/€/);
    await userEvent.selectOptions(screen.getByLabelText("Markt"), "DE+AT");
    expect(screen.getByText("Bestellwert (Einkauf)").closest("li")!.textContent).not.toMatch(/CHF/);
  });

  it("settings checkboxes build a custom selection, and an empty one is explained", async () => {
    await setup();
    await openTab(/Einstellungen/);
    await userEvent.click(screen.getByRole("checkbox", { name: "Schweiz" }));
    expect(screen.getByLabelText("Markt")).toHaveValue("DE+AT");
    await userEvent.click(screen.getByRole("checkbox", { name: "Österreich" }));
    expect(screen.getByLabelText("Markt")).toHaveValue("DE");
    await userEvent.click(screen.getByRole("checkbox", { name: "Deutschland" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Kein Markt");
    expect(JSON.parse(window.localStorage.getItem("freshcast.settings.v2")!).markets).toEqual([]);
  });

  it("currency checkbox hides one currency across markets", async () => {
    await setup();
    await openTab(/Einstellungen/);
    await userEvent.click(screen.getByRole("checkbox", { name: "CHF" }));
    await openTab(/Bestellungen/);
    expect(ordersRows()).toBe(40);
  });

  it("savings follow the selected market", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Markt"), "AT");
    await openTab(/Einsparungen/);
    expect(screen.getByRole("heading", { name: /Bestellregeln im Vergleich \(Österreich, EUR\)/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Schweiz/ })).not.toBeInTheDocument();
  });

  it("restores the market choice from the browser", async () => {
    window.localStorage.setItem("freshcast.settings.v2", JSON.stringify({ markets: ["CH"], costShare: 0.6, theme: "auto", role: "planner", workflow: {} }));
    await setup();
    await waitFor(() => expect(screen.getByLabelText("Markt")).toHaveValue("CH"));
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
  it.each([/^Heute$/, /Marktkarte/, /Übersicht/, /Filialvergleich/, /^Freigabe$/, /Preisaktionen/, /Einstellungen/, /Hilfe/, /Bestellungen/, /Prognose/, /Wochenplan/, /Warnungen/, /KI-Assistent/, /Warengruppen/, /Verfall/, /Was-wäre-wenn|What-if/, /Einsparungen/, /Daten/, /Modell/])(
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

describe("accessibility of the search dialog", () => {
  it("has no detectable violations while open", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    const results = await axe.run(screen.getByRole("dialog"), { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});

describe("retail chains and the market map", () => {
  const ordersRows = () => within(screen.getByRole("table")).getAllByRole("row").length - 1;

  it("the chain select narrows every tab and combines with the market", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText("Handelskette"), "PreisPunkt");
    await openTab(/Bestellungen/);
    expect(ordersRows()).toBe(24); // three stores x 8 SKUs
    await userEvent.selectOptions(screen.getByLabelText("Markt"), "AT");
    expect(ordersRows()).toBe(8);
  });

  it("the map lists a chain in each of its countries and a click filters to it", async () => {
    await setup();
    await openTab(/Marktkarte/);
    const table = screen.getByRole("table");
    const row = within(table).getByRole("row", { name: /PreisPunkt/ });
    expect(row).toHaveTextContent("3 Länder");
    expect(within(table).getByRole("row", { name: /MarktHaus/ })).toHaveTextContent("Nur in");
    await userEvent.click(within(row).getByRole("button", { name: /Schweiz/ }));
    expect(screen.getByLabelText("Handelskette")).toHaveValue("PreisPunkt");
    expect(screen.getByLabelText("Markt")).toHaveValue("CH");
    await openTab(/Bestellungen/);
    expect(ordersRows()).toBe(8);
    await openTab(/Marktkarte/);
    await userEvent.click(screen.getByRole("button", { name: "Alle Ketten und Märkte zeigen" }));
    expect(screen.getByLabelText("Handelskette")).toHaveValue("");
  });

  it("savings follow the chain filter and remember it in the browser", async () => {
    await setup();
    await openTab(/Einstellungen/);
    await userEvent.click(screen.getByRole("checkbox", { name: "AlpenFrisch" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "MarktHaus" }));
    expect(JSON.parse(window.localStorage.getItem("freshcast.settings.v2")!).chains).toEqual(["PreisPunkt"]);
    await openTab(/Einsparungen/);
    expect(screen.getAllByText(/Handelsketten: PreisPunkt/).length).toBeGreaterThan(0);
  });
});

describe("Today, quick search and paging", () => {
  it("Today lists open tasks with counts, jumps to the right tab and remembers ticks per day", async () => {
    const first = await landing();
    const list = within(screen.getByRole("heading", { name: /Heute zu tun/ }).closest("section")!);
    const approve = list.getByRole("checkbox", { name: /noch nicht eingereicht/ });
    expect(approve).not.toBeChecked();
    await userEvent.click(approve);
    expect(JSON.parse(window.localStorage.getItem("freshcast.today.v1")!).done).toContain("approve");
    first.unmount();
    await landing();
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /noch nicht eingereicht/ })).toBeChecked());
    await userEvent.click(screen.getAllByRole("button", { name: "Öffnen" })[0]!);
    expect(screen.getByRole("tab", { name: "Freigabe" })).toHaveAttribute("aria-selected", "true");
  });

  it("Ctrl+K opens the search, finds an item, Enter opens its forecast, Esc closes", async () => {
    await setup();
    await userEvent.keyboard("{Control>}k{/Control}");
    const dialog = screen.getByRole("dialog", { name: "Suchen und springen" });
    await userEvent.type(within(dialog).getByRole("combobox"), "lachs");
    expect(within(dialog).getAllByRole("option")[0]).toHaveTextContent(/Lachsfilet/);
    await userEvent.keyboard("{Enter}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("tab", { name: "Prognose" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the search finds sections too, and the slash key opens it outside of inputs", async () => {
    await setup();
    await userEvent.keyboard("/");
    const dialog = within(screen.getByRole("dialog"));
    await userEvent.type(dialog.getByRole("combobox"), "freigabe");
    await userEvent.click(dialog.getAllByRole("option")[0]!);
    expect(screen.getByRole("tab", { name: "Freigabe" })).toHaveAttribute("aria-selected", "true");
  });

  it("long tables are shown in pages with a show-more row", async () => {
    const big = { ...data, items: Array.from({ length: 5 }, (_, c) => data.items.map((it) => ({ ...it, store_id: it.store_id.replace(/-\d+$/, `-0${c + 1}`) }))).flat() };
    render(<Dashboard load={async () => big} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
    await openTab(/^Bestellungen$/);
    const rows = () => within(screen.getByRole("table")).getAllByRole("row").length;
    expect(rows()).toBe(1 + 100 + 1); // header, one page, show-more row
    await userEvent.click(screen.getByRole("button", { name: /Mehr anzeigen/ }));
    expect(rows()).toBeGreaterThan(102);
  });
});
