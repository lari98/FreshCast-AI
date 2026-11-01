import { formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { buildAlerts } from "@/lib/alerts";
import type { Alert } from "@/lib/alerts";
import type { Item, Lang } from "@/lib/types";

interface Props {
  items: Item[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

export function AlertsTab({ items, lang, t, onOpen }: Props) {
  const alerts = buildAlerts(items);
  const text: Record<Alert["kind"], string> = {
    expiry: t.alertExpiry, stockout: t.alertStockout, spike: t.alertSpike,
    drop: t.alertDrop, accuracy: t.alertAccuracy,
  };
  const value = (a: Alert) =>
    a.kind === "expiry" || a.kind === "stockout"
      ? `${formatNumber(a.value, lang)} ${t.units}`
      : formatPercent(a.value, lang, 0);
  const sev = { high: "■", medium: "▲" } as const;

  return (
    <section aria-labelledby="alerts-h" className="card">
      <h2 id="alerts-h">{t.alertsTitle} ({alerts.length})</h2>
      <p className="hint">{t.alertsHint}</p>
      {alerts.length === 0 ? (
        <p>{t.noAlerts}</p>
      ) : (
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.alertsTitle} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colSeverity}</th>
                <th scope="col">{t.colProduct}</th>
                <th scope="col">{t.colStore}</th>
                <th scope="col">{t.colAlert}</th>
                <th scope="col">{t.colValue2}</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td className={a.severity === "high" ? "risk risk-high" : "risk risk-medium"}>
                    <span aria-hidden="true">{sev[a.severity]} </span>
                    {a.severity === "high" ? t.severityHigh : t.severityMedium}
                  </td>
                  <th scope="row">
                    <button type="button" className="link" onClick={() => onOpen(a.key)}>{a.item.name[lang]}</button>
                  </th>
                  <td>{a.item.store_id}</td>
                  <td>{text[a.kind]}</td>
                  <td>{value(a)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
