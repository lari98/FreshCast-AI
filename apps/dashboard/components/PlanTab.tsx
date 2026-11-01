import { formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { future } from "@/lib/alerts";
import type { Item, Lang } from "@/lib/types";

interface Props {
  items: Item[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

const DAY = { de: "de-DE", en: "en-GB" } as const;

export function PlanTab({ items, lang, t, onOpen }: Props) {
  if (items.length === 0) return <p>{t.noItems}</p>;
  const dates = future(items[0]!).map((p) => p.date);
  const rows = items.map((item) => {
    const byDate = new Map(future(item).map((p) => [p.date, p]));
    const cells = dates.map((d) => byDate.get(d));
    const total = cells.reduce((s, c) => s + (c && c.is_open ? c.point : 0), 0);
    return { item, cells, total };
  });
  const max = Math.max(1, ...rows.flatMap((r) => r.cells.map((c) => (c && c.is_open ? c.point : 0))));
  const dayTotals = dates.map((_, i) =>
    rows.reduce((s, r) => s + (r.cells[i] && r.cells[i]!.is_open ? r.cells[i]!.point : 0), 0),
  );
  const head = (iso: string) =>
    new Intl.DateTimeFormat(DAY[lang], { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "UTC" })
      .format(new Date(`${iso}T00:00:00Z`));

  return (
    <section aria-labelledby="plan-h" className="card">
      <h2 id="plan-h">{t.planTitle}</h2>
      <p className="hint">{t.planHint}</p>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.planTitle} – ${t.tableLabel}`}>
        <table className="heat">
          <thead>
            <tr>
              <th scope="col">{t.colProduct}</th>
              <th scope="col">{t.colStore}</th>
              {dates.map((d) => <th key={d} scope="col">{head(d)}</th>)}
              <th scope="col">{t.colTotal}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ item, cells, total }) => (
              <tr key={`${item.store_id}|${item.sku}`}>
                <th scope="row">
                  <button type="button" className="link" onClick={() => onOpen(`${item.store_id}|${item.sku}`)}>
                    {item.name[lang]}
                  </button>
                </th>
                <td className="nowrap">{item.store_id}</td>
                {cells.map((c, i) => (
                  <td
                    key={dates[i]}
                    className="cell"
                    style={c && c.is_open ? { backgroundColor: `color-mix(in srgb, var(--accent) ${Math.round((c.point / max) * 55)}%, transparent)` } : undefined}
                  >
                    {c && c.is_open ? formatNumber(c.point, lang) : "–"}
                  </td>
                ))}
                <td><strong>{formatNumber(total, lang)}</strong></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>{t.dayTotal}</th>
              {dayTotals.map((v, i) => <td key={dates[i]}><strong>{formatNumber(v, lang)}</strong></td>)}
              <td><strong>{formatNumber(dayTotals.reduce((a, b) => a + b, 0), lang)}</strong></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
