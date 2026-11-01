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
import { PRESETS, availableChains, availableCurrencies, availableMarkets, filterMarkets, presetFor } from "@/lib/markets";
import { MapTab } from "./MapTab";
import { UpdateWatcher } from "./UpdateWatcher";
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
  "overview", "map", "stores", "alerts", "orders", "approval", "whatif", "forecast", "plan", "categories",
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
  // null = no restriction (all markets / all currencies in the data)
  const [marketSel, setMarketSel] = useState<string[] | null>(null);
  const [currencySel, setCurrencySel] = useState<string[] | null>(null);
  const [chainSel, setChainSel] = useState<string[] | null>(null);
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

  const allItems = useMemo(() => data?.items ?? [], [data]);
  const markets = useMemo(() => availableMarkets(allItems), [allItems]);
  const currencies = useMemo(() => availableCurrencies(allItems), [allItems]);
  const selMarkets = useMemo(() => new Set(marketSel ?? markets), [marketSel, markets]);
  const selCurrencies = useMemo(() => new Set(currencySel ?? currencies), [currencySel, currencies]);
  const chains = useMemo(() => availableChains(allItems), [allItems]);
  const selChains = useMemo(() => new Set(chainSel ?? chains), [chainSel, chains]);
  const marketItems = useMemo(
    () => filterMarkets(allItems, selMarkets, selCurrencies, selChains),
    [allItems, selMarkets, selCurrencies, selChains],
  );
  const stores = useMemo(
    () => [...new Map(marketItems.map((i) => [i.store_id, i.city])).entries()],
    [marketItems],
  );
  // A store that the market filter hides can no longer be the active scope.
  const activeStore = stores.some(([id]) => id === store) ? store : "";
  const scope = useMemo(
    () => marketItems.filter((i) => !activeStore || i.store_id === activeStore),
    [marketItems, activeStore],
  );
  const preset = presetFor(selMarkets, markets);
  const nothingSelected = allItems.length > 0 && marketItems.length === 0;
  const toggle = (list: string[], all: string[], value: string) => {
    const next = new Set(list);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return all.filter((x) => next.has(x));
  };
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
          const strings = (v: unknown) => (Array.isArray(v) && v.every((x) => typeof x === "string") ? (v as string[]) : null);
          setMarketSel(strings(raw.markets));
          setCurrencySel(strings(raw.currencies));
          setChainSel(strings(raw.chains));
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
        JSON.stringify({ costShare, theme, role, markets: marketSel, currencies: currencySel, chains: chainSel, workflow: data?.source === "upload" ? {} : workflow }),
      );
    } catch {
      /* Not persisted; the page still works. */
    }
  }, [restored, costShare, theme, role, marketSel, currencySel, chainSel, workflow, data]);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);

  const groups = [
    { label: t.groupOverview, tabs: [
      { id: "overview", label: t.tabOverview },
      { id: "map", label: t.tabMap },
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
      <UpdateWatcher t={t} busy={data?.source === "upload"} />
      <header className="top">
        <h1>{t.title}</h1>
        <div className="filters">
          {markets.length > 1 && (
            <label>
              {t.marketLabel}
              <select
                value={preset}
                onChange={(e) => {
                  const p = PRESETS.find((x) => x.id === e.target.value);
                  if (!p) return;
                  const chosen = markets.filter((m) => p.markets.includes(m));
                  setMarketSel(p.id === "all" ? null : chosen);
                  setCurrencySel(null);
                  setStore("");
                }}
              >
                {preset === "custom" && <option value="custom">{t.marketCustom}</option>}
                {PRESETS.filter((p) => p.id === "all" || p.markets.every((m) => markets.includes(m))).map((p) => (
                  <option key={p.id} value={p.id}>
                    {{ all: t.presetAll, DE: t.presetDE, AT: t.presetAT, CH: t.presetCH, "DE+AT": t.presetDEAT }[p.id]}
                  </option>
                ))}
              </select>
            </label>
          )}
          {chains.length > 1 && (
            <label>
              {t.chainLabel}
              <select
                value={selChains.size === chains.length ? "" : selChains.size === 1 ? [...selChains][0] : "custom"}
                onChange={(e) => {
                  setChainSel(e.target.value ? [e.target.value] : null);
                  setStore("");
                }}
              >
                {selChains.size > 1 && selChains.size < chains.length && <option value="custom">{t.marketCustom}</option>}
                <option value="">{t.chainAll}</option>
                {chains.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          )}
          <label>
            {t.scope}
            <select value={activeStore} onChange={(e) => setStore(e.target.value)}>
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
        {nothingSelected && <p role="alert">{t.marketsNone}</p>}
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
            {tab === "map" && (
              <MapTab
                metrics={allMetrics}
                markets={markets}
                selectedMarkets={selMarkets}
                selectedChains={selChains}
                onPick={(m, c) => { setMarketSel([m]); setChainSel([c]); setCurrencySel(null); setStore(""); }}
                onShowAll={() => { setMarketSel(null); setChainSel(null); setCurrencySel(null); setStore(""); }}
                lang={lang}
                t={t}
              />
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
                markets={markets} selectedMarkets={selMarkets}
                onToggleMarket={(m) => setMarketSel(toggle([...selMarkets], markets, m))}
                chains={chains} selectedChains={selChains}
                onToggleChain={(c) => setChainSel(toggle([...selChains], chains, c))}
                currencies={currencies} selectedCurrencies={selCurrencies}
                onToggleCurrency={(c) => setCurrencySel(toggle([...selCurrencies], currencies, c))}
                costShare={costShare} onCost={setCostShare} theme={theme} onTheme={setTheme}
                onReset={() => { setCostShare(COST_SHARE); setTheme("auto"); setMarketSel(null); setCurrencySel(null); setChainSel(null); }} t={t}
              />
            )}
            {tab === "help" && <HelpTab t={t} />}
            {tab === "whatif" && item && (
              <ScenariosTab key={key} item={item} scope={scope} lang={lang} t={t} costShare={costShare} />
            )}
            {tab === "savings" && (
              <SavingsTab replay={replay} failed={replayFailed} lang={lang} t={t} markets={selMarkets} chains={selChains} currencies={selCurrencies} />
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
      {process.env.NEXT_PUBLIC_BUILD && (
        <footer className="build">{t.build}: {process.env.NEXT_PUBLIC_BUILD}</footer>
      )}
    </>
  );
}
