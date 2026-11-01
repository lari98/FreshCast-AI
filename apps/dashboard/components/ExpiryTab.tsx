import { formatCurrency, formatDate, formatMoney, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { COST_SHARE, zeroMoney } from "@/lib/kpi";
import type { Item, Lang, Lot } from "@/lib/types";

interface Row {
  item: Item;
  lot: Lot;
  value: number;
}

interface Props {
  items: Item[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

const SYMBOL = { low: "●", medium: "▲", high: "■" } as const;

/** Rule-based hint, deliberately simple and labelled as such in the UI. */
function hint(lot: Lot, t: Strings): string {
  if (lot.days_left <= 1) return t.actMarkdown;
  if (lot.days_left <= 2) return t.actWatch;
  return t.actOk;
}

export function ExpiryTab({ items, lang, t, onOpen }: Props) {
  const rows: Row[] = items
    .flatMap((item) =>
      item.lots.map((lot) => ({ item, lot, value: lot.quantity * item.unit_price * COST_SHARE })),
    )
    .sort((a, b) => a.lot.days_left - b.lot.days_left || b.value - a.value);

  const risk = zeroMoney();
  for (const r of rows) if (r.lot.days_left <= 1) risk[r.item.currency] += r.value;

  if (rows.length === 0) return <p>{t.noItems}</p>;

  return (
    <section aria-labelledby="radar-h" className="card">
      <h2 id="radar-h">{t.expiryTitle}</h2>
      <p className="kpi-inline">
        <span className="kpi-label">{t.valueAtRisk}</span>{" "}
        <strong>{formatMoney(risk, lang)}</strong>
      </p>
      <p className="hint">{t.expiryRule}</p>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.expiryTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t.colProduct}</th>
              <th scope="col">{t.colStore}</th>
              <th scope="col">{t.qty}</th>
              <th scope="col">{t.useBy}</th>
              <th scope="col">{t.daysLeft}</th>
              <th scope="col">{t.colValue}</th>
              <th scope="col">{t.risk}</th>
              <th scope="col">{t.colAction}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ item, lot, value }) => (
              <tr key={`${item.store_id}|${item.sku}|${lot.lot_id}`}>
                <th scope="row">
                  <button type="button" className="link" onClick={() => onOpen(`${item.store_id}|${item.sku}`)}>
                    {item.name[lang]}
                  </button>
                </th>
                <td>{item.store_id}</td>
                <td>{formatNumber(lot.quantity, lang)}</td>
                <td>{formatDate(lot.use_by, lang)}</td>
                <td>{formatNumber(lot.days_left, lang)}</td>
                <td>{formatCurrency(value, item.currency, lang)}</td>
                <td className={`risk risk-${lot.risk}`}>
                  <span aria-hidden="true">{SYMBOL[lot.risk]} </span>
                  {t.risks[lot.risk]}
                </td>
                <td>{hint(lot, t)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
