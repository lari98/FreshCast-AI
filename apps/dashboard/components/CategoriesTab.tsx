import { formatMoney, formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { byCategory } from "@/lib/categories";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

interface Props {
  metrics: ItemMetrics[];
  lang: Lang;
  t: Strings;
}

export function CategoriesTab({ metrics, lang, t }: Props) {
  const rows = byCategory(metrics, t.otherCategory);
  if (rows.length === 0) return <p>{t.noItems}</p>;
  const maxRate = Math.max(0.0001, ...rows.map((r) => r.wasteRate ?? 0));
  return (
    <section aria-labelledby="cat-h" className="card">
      <h2 id="cat-h">{t.categoriesTitle}</h2>
      <p className="hint">{t.categoriesHint}</p>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.categoriesTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t.colCategory}</th>
              <th scope="col">{t.colItems}</th>
              <th scope="col">{t.colForecastUnits}</th>
              <th scope="col">{t.colRevenue}</th>
              <th scope="col">{t.colWasteRate}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.category}>
                <th scope="row">{t.categoryNames[r.category] ?? r.category}</th>
                <td>{formatNumber(r.items, lang)}</td>
                <td>{formatNumber(r.forecastUnits, lang)}</td>
                <td>{formatMoney(r.revenue, lang)}</td>
                <td>
                  <span className="bar-track inline" aria-hidden="true">
                    <span className="bar-fill" style={{ width: `${((r.wasteRate ?? 0) / maxRate) * 100}%` }} />
                  </span>{" "}
                  {formatPercent(r.wasteRate, lang)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
