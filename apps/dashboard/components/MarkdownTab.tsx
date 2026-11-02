"use client";

import { PagedRows } from "./PagedRows";
import { useMemo, useState } from "react";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { bestMarkdown, lotExcess, markdownOutcome } from "@/lib/markdown";
import type { Item, Lang } from "@/lib/types";

interface Props {
  items: Item[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

export function MarkdownTab({ items, lang, t, onOpen }: Props) {
  const [discount, setDiscount] = useState(0.3);
  const [elasticity, setElasticity] = useState(1.5);

  const rows = useMemo(() => items
    .map((item) => {
      const lots = lotExcess(item);
      const excess = lots.reduce((s, l) => s + l.excess, 0);
      return {
        item, excess,
        outcome: markdownOutcome(item.unit_price, lots, discount, elasticity),
        best: bestMarkdown(item.unit_price, lots, elasticity),
      };
    })
    .filter((r) => r.excess > 0)
    .sort((a, b) => b.excess * b.item.unit_price - a.excess * a.item.unit_price),
  [items, discount, elasticity]);

  const total = { EUR: 0, CHF: 0 };
  for (const r of rows) total[r.item.currency] += r.outcome.net;

  return (
    <section aria-labelledby="md-h" className="card">
      <h2 id="md-h">{t.mdTitle}</h2>
      <p className="hint">{t.mdHint}</p>
      <div className="sliders">
        <label>
          {t.mdDiscount}: <strong>{Math.round(discount * 100)} %</strong>
          <input type="range" min={10} max={70} step={10} value={Math.round(discount * 100)}
            onChange={(e) => setDiscount(Number(e.target.value) / 100)} />
        </label>
        <label>
          {t.mdElasticity}: <strong>{elasticity.toFixed(1)}</strong>
          <input type="range" min={0} max={3} step={0.5} value={elasticity}
            onChange={(e) => setElasticity(Number(e.target.value))} />
        </label>
      </div>
      {rows.length === 0 ? (
        <p>{t.mdNoExcess}</p>
      ) : (
        <>
          <p>
            <strong>{t.mdTotal}:</strong>{" "}
            {(["EUR", "CHF"] as const).filter((c) => total[c] !== 0).map((c) => formatCurrency(total[c], c, lang)).join(" · ") || formatCurrency(0, "EUR", lang)}
          </p>
          <div className="scroll" tabIndex={0} role="region" aria-label={`${t.mdTitle} – ${t.tableLabel}`}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t.colProduct}</th>
                  <th scope="col">{t.colStore}</th>
                  <th scope="col">{t.mdExcess}</th>
                  <th scope="col">{t.mdExtra}</th>
                  <th scope="col">{t.mdNet}</th>
                  <th scope="col">{t.mdBest}</th>
                </tr>
              </thead>
              <tbody>
                <PagedRows rows={rows} colSpan={8} t={t} render={(r) => (
                  <tr key={`${r.item.store_id}|${r.item.sku}`}>
                    <th scope="row">
                      <button type="button" className="link" onClick={() => onOpen(`${r.item.store_id}|${r.item.sku}`)}>
                        {r.item.name[lang]}
                      </button>
                    </th>
                    <td className="nowrap">{r.item.store_id}</td>
                    <td>{formatNumber(r.excess, lang)} {t.units}</td>
                    <td>{formatNumber(r.outcome.extraUnits, lang)} {t.units}</td>
                    <td className={r.outcome.net < 0 ? "risk risk-high" : undefined}>
                      <span aria-hidden="true">{r.outcome.net < 0 ? "▼ " : "▲ "}</span>
                      {formatCurrency(r.outcome.net, r.item.currency, lang)}
                    </td>
                    <td>{r.best ? formatPercent(r.best.markdown, lang, 0) : t.mdNone}</td>
                  </tr>
                )} />
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
