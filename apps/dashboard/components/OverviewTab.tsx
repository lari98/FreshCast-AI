import { formatMoney, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { attentionList, totals } from "@/lib/kpi";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

interface Props {
  metrics: ItemMetrics[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

export function OverviewTab({ metrics, lang, t, onOpen }: Props) {
  if (metrics.length === 0) return <p>{t.noItems}</p>;
  const sum = totals(metrics);
  const list = attentionList(metrics);
  const top = [...metrics].sort((a, b) => b.wasteCost - a.wasteCost).slice(0, 8);
  const maxWaste = Math.max(1, ...top.map((m) => m.wasteCost));

  const kpis: { label: string; value: string; note?: string; tone: string }[] = [
    { label: t.kpiOrderCost, value: formatMoney(sum.orderCost, lang), tone: "accent" },
    {
      label: t.kpiToOrder,
      value: `${formatNumber(sum.itemsToOrder, lang)} ${t.kpiOf} ${formatNumber(sum.items, lang)}`,
      tone: "ok",
    },
    { label: t.kpiAtRisk, value: formatMoney(sum.atRiskCost, lang), tone: "crit" },
    { label: t.kpiWaste, value: formatMoney(sum.wasteCost, lang), note: t.kpiOutlook, tone: "warn" },
    { label: t.kpiLost, value: formatMoney(sum.lostMargin, lang), note: t.kpiOutlook, tone: "warn" },
  ];

  return (
    <>
      <ul className="kpis">
        {kpis.map((k) => (
          <li key={k.label} className={`kpi tone-${k.tone}`}>
            <span className="kpi-label">{k.label}</span>
            <span className="kpi-value">{k.value}</span>
            {k.note && <span className="kpi-note">{k.note}</span>}
          </li>
        ))}
      </ul>
      <p className="hint">{t.costAssumption}</p>

      <div className="grid-2 even">
        <section aria-labelledby="attn-h" className="card">
          <h2 id="attn-h">{t.attentionTitle}</h2>
          <p className="hint">{t.attentionHint}</p>
          <ol className="rank">
            {list.map((m) => (
              <li key={m.key}>
                <button type="button" className="link" onClick={() => onOpen(m.key)}>
                  {m.item.name[lang]} <span className="muted">· {m.item.store_id}</span>
                </button>
                <span className="rank-values">
                  <span className={`risk risk-${m.worstRisk}`}>{t.risks[m.worstRisk]}</span>
                  <span>
                    {formatMoney(
                      m.item.currency === "EUR"
                        ? { EUR: m.attention + m.atRiskCost, CHF: 0 }
                        : { EUR: 0, CHF: m.attention + m.atRiskCost },
                      lang,
                    )}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="waste-h" className="card">
          <h2 id="waste-h">{t.wasteTop}</h2>
          <ul className="bars">
            {top.map((m) => (
              <li key={m.key}>
                <span className="bar-label">
                  {m.item.name[lang]} <span className="muted">{m.item.store_id}</span>
                </span>
                <span className="bar-track" aria-hidden="true">
                  <span className="bar-fill" style={{ width: `${(m.wasteCost / maxWaste) * 100}%` }} />
                </span>
                <span className="bar-value">
                  {formatMoney(
                    m.item.currency === "EUR" ? { EUR: m.wasteCost, CHF: 0 } : { EUR: 0, CHF: m.wasteCost },
                    lang,
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
