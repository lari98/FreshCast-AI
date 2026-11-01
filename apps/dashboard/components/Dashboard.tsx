"use client";

import { useEffect, useMemo, useState } from "react";
import { loadData } from "@/lib/source";
import { STRINGS } from "@/lib/i18n";
import type { DashboardData, Lang } from "@/lib/types";
import { ExpiryTable } from "./ExpiryTable";
import { ForecastChart } from "./ForecastChart";
import { ProposalCard } from "./ProposalCard";

interface Props {
  /** Injected in tests; defaults to the demo/API loader. */
  load?: () => Promise<DashboardData>;
}

export function Dashboard({ load = () => loadData() }: Props) {
  const [lang, setLang] = useState<Lang>("de");
  const [data, setData] = useState<DashboardData | null>(null);
  const [failed, setFailed] = useState(false);
  const [store, setStore] = useState<string>("");
  const [sku, setSku] = useState<string>("");
  const t = STRINGS[lang];

  useEffect(() => {
    let cancelled = false;
    load()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setStore(d.items[0]?.store_id ?? "");
        setSku(d.items[0]?.sku ?? "");
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stores = useMemo(
    () => [...new Map((data?.items ?? []).map((i) => [i.store_id, i.city])).entries()],
    [data],
  );
  const products = useMemo(
    () => (data?.items ?? []).filter((i) => i.store_id === store),
    [data, store],
  );
  const item = products.find((i) => i.sku === sku) ?? products[0];

  return (
    <>
      <a className="skip" href="#main">{t.skip}</a>
      <header className="top">
        <h1>{t.title}</h1>
        <label>
          {t.language}
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </label>
      </header>
      <p className="banner" role="note">{t.demoBanner}</p>
      <main id="main" tabIndex={-1}>
        {failed && <p role="alert">{t.error}</p>}
        {!data && !failed && <p role="status">{t.loading}</p>}
        {data && item && (
          <>
            <div className="filters">
              <label>
                {t.store}
                <select
                  value={store}
                  onChange={(e) => {
                    setStore(e.target.value);
                    setSku(data.items.find((i) => i.store_id === e.target.value)?.sku ?? "");
                  }}
                >
                  {stores.map(([id, city]) => (
                    <option key={id} value={id}>{`${city} (${id})`}</option>
                  ))}
                </select>
              </label>
              <label>
                {t.product}
                <select value={item.sku} onChange={(e) => setSku(e.target.value)}>
                  {products.map((i) => (
                    <option key={i.sku} value={i.sku}>{i.name[lang]}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid-2">
              <ForecastChart series={item.series} lang={lang} t={t} asOf={data.as_of} />
              <ProposalCard
                proposal={item.proposal}
                explanation={item.explanation[lang]}
                lang={lang}
                t={t}
              />
            </div>
            <ExpiryTable lots={item.lots} lang={lang} t={t} />
          </>
        )}
      </main>
    </>
  );
}
