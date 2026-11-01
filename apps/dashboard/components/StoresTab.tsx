import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { ItemMetrics } from "@/lib/kpi";
import { byStore } from "@/lib/stores";
import type { Lang } from "@/lib/types";

interface Props {
  metrics: ItemMetrics[];
  lang: Lang;
  t: Strings;
}

export function StoresTab({ metrics, lang, t }: Props) {
  const rows = byStore(metrics).sort((a, b) => (b.lossRatio ?? 0) - (a.lossRatio ?? 0));
  if (rows.length === 0) return <p>{t.noItems}</p>;
  const max = Math.max(0.0001, ...rows.map((r) => r.lossRatio ?? 0));
  return (
    <section aria-labelledby="stores-h" className="card">
      <h2 id="stores-h">{t.storesTitle}</h2>
      <p className="hint">{t.storesHint}</p>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.storesTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t.colStore}</th>
              <th scope="col">{t.colItemsToOrder}</th>
              <th scope="col">{t.kpiOrderCost}</th>
              <th scope="col">{t.kpiWaste}</th>
              <th scope="col">{t.kpiLost}</th>
              <th scope="col">{t.colAlerts}</th>
              <th scope="col">{t.colAccuracy}</th>
              <th scope="col">{t.colLossRatio}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.storeId}>
                <th scope="row">{r.city} <span className="muted">{r.storeId}</span></th>
                <td>{formatNumber(r.itemsToOrder, lang)} / {formatNumber(r.items, lang)}</td>
                <td>{formatCurrency(r.orderCost, r.currency, lang)}</td>
                <td>{formatCurrency(r.wasteCost, r.currency, lang)}</td>
                <td>{formatCurrency(r.lostMargin, r.currency, lang)}</td>
                <td>{formatNumber(r.alerts, lang)}</td>
                <td>{formatPercent(r.accuracy.wape, lang)}</td>
                <td>
                  <span className="bar-track inline" aria-hidden="true">
                    <span className="bar-fill warn" style={{ width: `${((r.lossRatio ?? 0) / max) * 100}%` }} />
                  </span>{" "}
                  {formatPercent(r.lossRatio, lang)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
