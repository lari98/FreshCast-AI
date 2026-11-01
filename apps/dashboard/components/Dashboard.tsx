"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadData } from "@/lib/source";
import { STRINGS } from "@/lib/i18n";
import { itemKey, itemMetrics } from "@/lib/kpi";
import type { DashboardData, Lang } from "@/lib/types";
import { loadReplay as defaultLoadReplay } from "@/lib/replay";
import type { Replay } from "@/lib/replay";
import { SavingsTab } from "./SavingsTab";
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

const TAB_IDS = ["overview", "orders", "forecast", "plan", "alerts", "assistant", "expiry", "categories", "whatif", "savings", "data", "model"] as const;
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
  const [approved, setApproved] = useState<ReadonlySet<string>>(new Set());
  const [tab, setTab] = useState<TabId>("overview");
  const t = STRINGS[lang];

  const show = useCallback((d: DashboardData) => {
    setData(d);
    setStore("");
    setSelected(d.items[0] ? itemKey(d.items[0]) : "");
    setApproved(new Set());
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
  const metrics = useMemo(() => scope.map(itemMetrics), [scope]);
  const item = scope.find((i) => itemKey(i) === selected) ?? scope[0];
  const key = item ? itemKey(item) : "";

  function openForecast(k: string) {
    setSelected(k);
    changeTab("forecast");
  }
  const approve = (keys: string[]) =>
    setApproved((prev) => new Set([...prev, ...keys]));

  const tabs = [
    { id: "overview", label: t.tabOverview },
    { id: "orders", label: t.tabOrders },
    { id: "forecast", label: t.tabForecast },
    { id: "plan", label: t.tabPlan },
    { id: "alerts", label: t.tabAlerts },
    { id: "assistant", label: t.tabAssistant },
    { id: "expiry", label: t.tabExpiry },
    { id: "categories", label: t.tabCategories },
    { id: "whatif", label: t.tabScenarios },
    { id: "savings", label: t.tabSavings },
    { id: "data", label: t.tabData },
    { id: "model", label: t.tabModel },
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
          <Tabs tabs={tabs} active={tab} onChange={changeTab} label={t.tabsLabel}>
            {tab === "overview" && (
              <OverviewTab metrics={metrics} lang={lang} t={t} onOpen={openForecast} />
            )}
            {tab === "orders" && (
              <OrdersTab
                metrics={metrics}
                approved={approved}
                onApprove={approve}
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
                approved={approved.has(key)}
                onApprove={() => approve([key])}
                lang={lang}
                t={t}
              />
            )}
            {tab === "plan" && <PlanTab items={scope} lang={lang} t={t} onOpen={openForecast} />}
            {tab === "alerts" && <AlertsTab items={scope} lang={lang} t={t} onOpen={openForecast} />}
            {tab === "assistant" && (
              <AssistantTab metrics={metrics} lang={lang} t={t} onOpen={openForecast} />
            )}
            {tab === "categories" && <CategoriesTab metrics={metrics} lang={lang} t={t} />}
            {tab === "expiry" && (
              <ExpiryTab items={scope} lang={lang} t={t} onOpen={openForecast} />
            )}
            {tab === "whatif" && item && (
              <ScenariosTab key={key} item={item} scope={scope} lang={lang} t={t} />
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
