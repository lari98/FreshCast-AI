"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadData } from "@/lib/source";
import { STRINGS } from "@/lib/i18n";
import { itemKey, itemMetrics } from "@/lib/kpi";
import type { DashboardData, Lang } from "@/lib/types";
import { loadReplay as defaultLoadReplay } from "@/lib/replay";
import type { Replay } from "@/lib/replay";
import { SavingsTab } from "./SavingsTab";
import { ApprovalTab } from "./ApprovalTab";
import { HelpTab } from "./HelpTab";
import { MarkdownTab } from "./MarkdownTab";
import { SettingsTab } from "./SettingsTab";
import type { Theme } from "./SettingsTab";
import { StoresTab } from "./StoresTab";
import { COST_SHARE } from "@/lib/kpi";
import type { ItemMetrics } from "@/lib/kpi";
import { decide, parseWorkflow, setQuantity, setReason, submit } from "@/lib/workflow";
import type { Reason, Role, Workflow } from "@/lib/workflow";
import { AlertsTab } from "./AlertsTab";
import { AssistantTab } from "./AssistantTab";
import { CategoriesTab } from "./CategoriesTab";
import { PlanTab } from "./PlanTab";
import { DataTab } from "./DataTab";
import { ExpiryTab } from "./ExpiryTab";
import { ForecastTab } from "./ForecastTab";
import { ModelTab } from "./ModelTab";
import { OrdersTab } from "./OrdersTab";
import { OverviewTab } from "./OverviewTab";
import { ScenariosTab } from "./ScenariosTab";
import { Tabs } from "./Tabs";

interface Props {
  /** Injected in tests; defaults to the demo/API loader. */
  load?: () => Promise<DashboardData>;
  /** Policy replay (Savings tab); defaults to the bundled demo file. */
  loadReplay?: () => Promise<Replay>;
}

const TAB_IDS = [
  "overview", "stores", "alerts", "orders", "approval", "whatif", "forecast", "plan", "categories",
  "expiry", "markdown", "savings", "assistant", "model", "data", "settings", "help",
] as const;
const STORAGE_KEY = "freshcast.settings.v2";
type TabId = (typeof TAB_IDS)[number];

function tabFromHash(): TabId {
  try {
    const h = window.location.hash.replace("#", "");
    return (TAB_IDS as readonly string[]).includes(h) ? (h as TabId) : "overview";
  } catch {
    return "overview";
  }
}

export function Dashboard({ load = () => loadData(), loadReplay = () => defaultLoadReplay() }: Props) {
  const [lang, setLang] = useState<Lang>("de");
  const [data, setData] = useState<DashboardData | null>(null);
  const [demo, setDemo] = useState<DashboardData | null>(null);
  const [failed, setFailed] = useState(false);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [replayFailed, setReplayFailed] = useState(false);
  const [store, setStore] = useState<string>(""); // "" = all stores
  const [selected, setSelected] = useState<string>("");
  const [workflow, setWorkflow] = useState<Workflow>({});
  const [role, setRole] = useState<Role>("planner");
  const [costShare, setCostShare] = useState(COST_SHARE);
  const [theme, setTheme] = useState<Theme>("auto");
  const [restored, setRestored] = useState(false);
  const [tab, setTab] = useState<TabId>("overview");
  const t = STRINGS[lang];

  const show = useCallback((d: DashboardData) => {
    setData(d);
    setStore("");
    setSelected(d.items[0] ? itemKey(d.items[0]) : "");
    setWorkflow({});
  }, []);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((d) => {
        if (cancelled) return;
        setDemo(d);
        show(d);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadReplay()
      .then((r) => !cancelled && setReplay(r))
      .catch(() => !cancelled && setReplayFailed(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tab <-> URL hash, so a tab can be bookmarked or shared.
  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    queueMicrotask(onHash); // read the initial hash after hydration
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function changeTab(id: string) {
    setTab(id as TabId);
    try {
      window.history.replaceState(null, "", `#${id}`);
    } catch {
      /* Some embedded viewers forbid history changes; the tab still switches. */
    }
  }

  const stores = useMemo(
    () => [...new Map((data?.items ?? []).map((i) => [i.store_id, i.city])).entries()],
    [data],
  );
  const scope = useMemo(
    () => (data?.items ?? []).filter((i) => !store || i.store_id === store),
    [data, store],
  );
  const metrics = useMemo(() => scope.map((i) => itemMetrics(i, costShare)), [scope, costShare]);
  const item = scope.find((i) => itemKey(i) === selected) ?? scope[0];
  const key = item ? itemKey(item) : "";

  function openForecast(k: string) {
    setSelected(k);
    changeTab("forecast");
  }
  const allMetrics = useMemo(
    () => (data?.items ?? []).map((i) => itemMetrics(i, costShare)),
    [data, costShare],
  );
  const lookup = (k: string) => {
    const m = allMetrics.find((x) => x.key === k);
    return { proposed: m?.orderUnits ?? 0, packSize: m?.item.proposal.order_multiple ?? 1 };
  };
  const onSubmit = (keys: string[]) => setWorkflow((wf) => submit(wf, keys, lookup));
  const onDecide = (keys: string[], ok: boolean) => setWorkflow((wf) => decide(wf, keys, role, ok));
  const onQty = (m: ItemMetrics, qty: number) =>
    setWorkflow((wf) => setQuantity(wf, m.key, m.orderUnits, m.item.proposal.order_multiple, qty));
  const onReason = (k: string, reason: Reason | undefined) =>
    setWorkflow((wf) => setReason(wf, k, reason));

  // Restore settings and the order workflow (demo data only) from this browser.
  useEffect(() => {
    queueMicrotask(() => {
      try {
        const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null");
        if (raw && typeof raw === "object") {
          if (typeof raw.costShare === "number" && raw.costShare >= 0.4 && raw.costShare <= 0.8) setCostShare(raw.costShare);
          if (["auto", "light", "dark"].includes(raw.theme)) setTheme(raw.theme);
          if (raw.role === "reviewer" || raw.role === "planner") setRole(raw.role);
          setWorkflow(parseWorkflow(raw.workflow));
        }
      } catch {
        /* Storage can be blocked (private window, embedded viewer); start fresh. */
      }
      setRestored(true);
    });
  }, []);
  useEffect(() => {
    if (!restored) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ costShare, theme, role, workflow: data?.source === "upload" ? {} : workflow }),
      );
    } catch {
      /* Not persisted; the page still works. */
    }
  }, [restored, costShare, theme, role, workflow, data]);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);

  const groups = [
    { label: t.groupOverview, tabs: [
      { id: "overview", label: t.tabOverview },
      { id: "stores", label: t.tabStores },
      { id: "alerts", label: t.tabAlerts },
    ] },
    { label: t.groupOrdering, tabs: [
      { id: "orders", label: t.tabOrders },
      { id: "approval", label: t.tabApproval },
      { id: "whatif", label: t.tabScenarios },
    ] },
    { label: t.groupForecast, tabs: [
      { id: "forecast", label: t.tabForecast },
      { id: "plan", label: t.tabPlan },
      { id: "categories", label: t.tabCategories },
    ] },
    { label: t.groupFresh, tabs: [
      { id: "expiry", label: t.tabExpiry },
      { id: "markdown", label: t.tabMarkdown },
    ] },
    { label: t.groupAnalysis, tabs: [
      { id: "savings", label: t.tabSavings },
      { id: "assistant", label: t.tabAssistant },
      { id: "model", label: t.tabModel },
    ] },
    { label: t.groupSystem, tabs: [
      { id: "data", label: t.tabData },
      { id: "settings", label: t.tabSettings },
      { id: "help", label: t.tabHelp },
    ] },
  ];

  return (
    <>
      <a className="skip" href="#main">{t.skip}</a>
      <header className="top">
        <h1>{t.title}</h1>
        <div className="filters">
          <label>
            {t.scope}
            <select value={store} onChange={(e) => setStore(e.target.value)}>
              <option value="">{t.allStores}</option>
              {stores.map(([id, city]) => (
                <option key={id} value={id}>{city === id ? id : `${city} (${id})`}</option>
              ))}
            </select>
          </label>
          <label>
            {t.language}
            <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
      </header>
      <p className="banner" role="note">
        {data?.source === "upload" ? t.uploadBanner : t.demoBanner}
      </p>
      <main id="main" tabIndex={-1}>
        {failed && <p role="alert">{t.error}</p>}
        {!data && !failed && <p role="status">{t.loading}</p>}
        {data && (
          <Tabs groups={groups} active={tab} onChange={changeTab} label={t.tabsLabel}>
            {tab === "overview" && (
              <OverviewTab metrics={metrics} lang={lang} t={t} onOpen={openForecast} />
            )}
            {tab === "orders" && (
              <OrdersTab
                metrics={metrics}
                workflow={workflow}
                costShare={costShare}
                onSubmit={onSubmit}
                onOpen={openForecast}
                lang={lang}
                t={t}
              />
            )}
            {(tab === "forecast" || tab === "whatif") && scope.length > 0 && item && (
              <div className="filters">
                <label>
                  {t.pickItem}
                  <select value={key} onChange={(e) => setSelected(e.target.value)}>
                    {scope.map((i) => (
                      <option key={itemKey(i)} value={itemKey(i)}>
                        {i.name[lang]} · {i.store_id}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {tab === "forecast" && item && (
              <ForecastTab
                item={item}
                scope={scope}
                asOf={data.as_of}
                approved={workflow[key]?.status === "submitted" || workflow[key]?.status === "approved"}
                onApprove={() => onSubmit([key])}
                lang={lang}
                t={t}
              />
            )}
            {tab === "plan" && <PlanTab items={scope} lang={lang} t={t} onOpen={openForecast} />}
            {tab === "alerts" && <AlertsTab items={scope} lang={lang} t={t} onOpen={openForecast} />}
            {tab === "assistant" && (
              <AssistantTab metrics={metrics} lang={lang} t={t} onOpen={openForecast} />
            )}
            {tab === "categories" && <CategoriesTab metrics={metrics} lang={lang} t={t} costShare={costShare} />}
            {tab === "expiry" && (
              <ExpiryTab items={scope} lang={lang} t={t} onOpen={openForecast} costShare={costShare} />
            )}
            {tab === "stores" && <StoresTab metrics={metrics} lang={lang} t={t} />}
            {tab === "approval" && (
              <ApprovalTab
                metrics={metrics} workflow={workflow} role={role} costShare={costShare}
                onRole={setRole} onQty={onQty} onReason={onReason} onSubmit={onSubmit}
                onDecide={onDecide} onOpen={openForecast} lang={lang} t={t}
              />
            )}
            {tab === "markdown" && <MarkdownTab items={scope} lang={lang} t={t} onOpen={openForecast} />}
            {tab === "settings" && (
              <SettingsTab
                costShare={costShare} onCost={setCostShare} theme={theme} onTheme={setTheme}
                onReset={() => { setCostShare(COST_SHARE); setTheme("auto"); }} t={t}
              />
            )}
            {tab === "help" && <HelpTab t={t} />}
            {tab === "whatif" && item && (
              <ScenariosTab key={key} item={item} scope={scope} lang={lang} t={t} costShare={costShare} />
            )}
            {tab === "savings" && (
              <SavingsTab replay={replay} failed={replayFailed} lang={lang} t={t} />
            )}
            {tab === "data" && (
              <DataTab
                data={data}
                onData={show}
                onReset={() => demo && show(demo)}
                lang={lang}
                t={t}
              />
            )}
            {tab === "model" && <ModelTab lang={lang} t={t} />}
            {(tab === "forecast" || tab === "whatif") && scope.length === 0 && <p>{t.noItems}</p>}
          </Tabs>
        )}
      </main>
    </>
  );
}
