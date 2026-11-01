import { formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { accuracy, pooledAccuracy } from "@/lib/accuracy";
import type { Accuracy } from "@/lib/accuracy";
import type { DashboardData, Item, Lang } from "@/lib/types";
import { ForecastChart } from "./ForecastChart";
import { ProposalCard } from "./ProposalCard";

interface Props {
  item: Item;
  scope: Item[];
  asOf: DashboardData["as_of"];
  approved: boolean;
  onApprove: () => void;
  lang: Lang;
  t: Strings;
}

function AccuracyRow({ label, a, lang }: { label: string; a: Accuracy; lang: Lang }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{formatPercent(a.wape, lang)}</td>
      <td>{formatPercent(a.bias, lang)}</td>
      <td>{formatPercent(a.coverage, lang, 0)}</td>
      <td>{formatNumber(a.days, lang)}</td>
    </tr>
  );
}

export function ForecastTab({ item, scope, asOf, approved, onApprove, lang, t }: Props) {
  return (
    <>
      <div className="grid-2">
        <ForecastChart series={item.series} lang={lang} t={t} asOf={asOf} />
        <ProposalCard
          proposal={item.proposal}
          explanation={item.explanation[lang]}
          lang={lang}
          t={t}
          approved={approved}
          onApprove={onApprove}
        />
      </div>
      <section aria-labelledby="acc-h" className="card">
        <h2 id="acc-h">{t.accuracyTitle}</h2>
        <p className="hint">{t.accuracyHint}</p>
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.accuracyTitle} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">{t.scope}</span></th>
                <th scope="col">{t.wape}</th>
                <th scope="col">{t.bias}</th>
                <th scope="col">{t.coverage}</th>
                <th scope="col">{t.daysEvaluated}</th>
              </tr>
            </thead>
            <tbody>
              <AccuracyRow label={t.thisItem} a={accuracy(item.series)} lang={lang} />
              <AccuracyRow
                label={t.allItems}
                a={pooledAccuracy(scope.map((i) => i.series))}
                lang={lang}
              />
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
