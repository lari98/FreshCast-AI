import { formatDate, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { Lang, Lot } from "@/lib/types";

interface Props {
  lots: Lot[];
  lang: Lang;
  t: Strings;
}

/** Stock lots sorted by use-by date. Risk is shown as text + symbol, not colour alone. */
export function ExpiryTable({ lots, lang, t }: Props) {
  const symbol = { ok: "●", watch: "▲", critical: "■" } as const;
  const sorted = [...lots].sort((a, b) => a.use_by.localeCompare(b.use_by));
  return (
    <section aria-labelledby="lots-h" className="card">
      <h2 id="lots-h">{t.lotsTitle}</h2>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.lotsTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t.lot}</th>
              <th scope="col">{t.qty}</th>
              <th scope="col">{t.useBy}</th>
              <th scope="col">{t.daysLeft}</th>
              <th scope="col">{t.risk}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((lot) => (
              <tr key={lot.lot_id}>
                <th scope="row">{lot.lot_id}</th>
                <td>{formatNumber(lot.quantity, lang)}</td>
                <td>{formatDate(lot.use_by, lang)}</td>
                <td>{formatNumber(lot.days_left, lang)}</td>
                <td className={`risk risk-${lot.risk}`}>
                  <span aria-hidden="true">{symbol[lot.risk]} </span>
                  {t.risks[lot.risk]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
