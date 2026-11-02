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
import { StoresTab } from "./StoresTab";
import { PRESETS, availableChains, availableCurrencies, availableMarkets, filterMarkets, presetFor } from "@/lib/markets";
import { MapTab } from "./MapTab";
import { QuickSearch } from "./QuickSearch";
import type { SearchEntry } from "./QuickSearch";
import { TodayTab } from "./TodayTab";
import { UpdateWatcher } from "./UpdateWatcher";
import { COST_SHARE } from "@/lib/kpi";
import type { ItemMetrics } from "@/lib/kpi";
import { append, diffWorkflow } from "@/lib/audit";
import { decide, setQuantity, setReason, submit } from "@/lib/workflow";
import type { Reason, Workflow } from "@/lib/workflow";
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
import { useHashTab } from "./useHashTab";
import { useSettings } from "./useSettings";

interface Props {
  /** Injected in tests; defaults to the demo/API loader. */
  load?: () => Promise<DashboardData>;
  /** Policy replay (Savings tab); defaults to the bundled demo file. */
  loadReplay?: () => Promise<Replay>;
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
  const [tab, changeTab] = useHashTab();
  const t = STRINGS[lang];
  const {
    workflow, setWorkflow, role, setRole, costShare, setCostShare, theme, setTheme,
    marketSel, setMarketSel, currencySel, setCurrencySel, chainSel, setChainSel, audit, setAudit,
  } = useSettings(data?.source === "upload");

  const show = useCallback((d: DashboardData) => {
    setData(d);
    setStore("");
    setSelected(d.items[0] ? itemKey(d.items[0]) : "");
    setWorkflow({});
  }, [setWorkflow]);

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
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target as HTMLElement | null)?.tagName ?? "");
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const preset = presetFor(selMarkets, markets);
  const nothingSelected = allItems.length > 0 && marketItems.length === 0;
  const toggle = (list: string[], all: string[], value: string) => {
    const next = new Set(list);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return all.filter((x) => next.has(x));
  };
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
  // Metrics are computed once for every item; the filtered view just picks from them.
  const metrics = useMemo(() => {
    const keys = new Set(scope.map(itemKey));
    return allMetrics.filter((m) => keys.has(m.key));
  }, [scope, allMetrics]);
  const lookup = (k: string) => {
    const m = allMetrics.find((x) => x.key === k);
    return { proposed: m?.orderUnits ?? 0, packSize: m?.item.proposal.order_multiple ?? 1 };
  };
  // Every status change is also written to the local decision history.
  const commit = (next: Workflow) => {
    setAudit((log) => append(log, diffWorkflow(workflow, next, role, new Date().toISOString())));
    setWorkflow(next);
  };
  const onSubmit = (keys: string[]) => commit(submit(workflow, keys, lookup));
  const onDecide = (keys: string[], ok: boolean) => commit(decide(workflow, keys, role, ok));
  const onQty = (m: ItemMetrics, qty: number) =>
    setWorkflow((wf) => setQuantity(wf, m.key, m.orderUnits, m.item.proposal.order_multiple, qty));
  const onReason = (k: string, reason: Reason | undefined) =>
    setWorkflow((wf) => setReason(wf, k, reason));

  const groups = [
    { label: t.groupOverview, tabs: [
      { id: "today", label: t.tabToday },
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

  const searchEntries: SearchEntry[] = [
    ...groups.flatMap((g) => g.tabs.map((x) => ({ id: x.id, kind: "tab" as const, label: x.label, sub: g.label }))),
    ...scope.map((i) => ({ id: itemKey(i), kind: "item" as const, label: i.name[lang], sub: `${i.store_id}${i.chain ? ` · ${i.chain}` : ""}` })),
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
          <button type="button" className="btn" onClick={() => setSearchOpen(true)}>{t.searchOpen}</button>
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
            {tab === "today" && (
              <TodayTab
                metrics={metrics} items={scope} workflow={workflow} role={role} asOf={data.as_of}
                lang={lang} t={t} onGo={changeTab}
              />
            )}
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
                onDecide={onDecide} onOpen={openForecast} audit={audit} lang={lang} t={t}
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
      {searchOpen && (
        <QuickSearch
          entries={searchEntries}
          t={t}
          onClose={() => setSearchOpen(false)}
          onPick={(e) => {
            setSearchOpen(false);
            if (e.kind === "tab") changeTab(e.id);
            else openForecast(e.id);
          }}
        />
      )}
      {process.env.NEXT_PUBLIC_BUILD && (
        <footer className="build">{t.build}: {process.env.NEXT_PUBLIC_BUILD}</footer>
      )}
    </>
  );
}
