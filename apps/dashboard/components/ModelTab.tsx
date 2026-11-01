import { formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { BACKTEST, SCALE } from "@/lib/modelFacts";
import type { Lang } from "@/lib/types";

interface Props {
  lang: Lang;
  t: Strings;
}

export function ModelTab({ lang, t }: Props) {
  const secs = (v: number | null) => (v === null ? `– (${t.reusedModel})` : `${formatNumber(v, lang)} s`);
  const bars = [
    { label: t.baselineModel, value: BACKTEST.wapeBaseline },
    { label: t.boostedModel, value: BACKTEST.wapeModel },
  ];
  return (
    <>
      <section aria-labelledby="bench-h" className="card">
        <h2 id="bench-h">{t.benchTitle}</h2>
        <ul className="bars">
          {bars.map((b) => (
            <li key={b.label}>
              <span className="bar-label">{b.label}</span>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(b.value / BACKTEST.wapeBaseline) * 100}%` }} />
              </span>
              <span className="bar-value">{t.wape} {formatPercent(b.value, lang)}</span>
            </li>
          ))}
        </ul>
        <dl className="facts">
          <div><dt>{t.biasLabel}</dt><dd>{formatPercent(BACKTEST.bias, lang)}</dd></div>
          <div>
            <dt>{t.coverageLabel}</dt>
            <dd>
              {formatPercent(BACKTEST.coverage, lang)} ({t.coverageBefore}: {formatPercent(BACKTEST.coverageBeforeCalibration, lang)})
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="scale-h" className="card">
        <h2 id="scale-h">{t.scaleTitle}</h2>
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.scaleTitle} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colSeries}</th>
                <th scope="col">{t.colFeatures}</th>
                <th scope="col">{t.colTrain}</th>
                <th scope="col">{t.colPredict}</th>
              </tr>
            </thead>
            <tbody>
              {SCALE.map((r) => (
                <tr key={r.series}>
                  <th scope="row">{formatNumber(r.series, lang)}</th>
                  <td>{formatNumber(r.features, lang)} s</td>
                  <td>{secs(r.train)}</td>
                  <td>{formatNumber(r.predict, lang)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="guard-h" className="card">
        <h2 id="guard-h">{t.principlesTitle}</h2>
        <ul>
          <li>{t.principle1}</li>
          <li>{t.principle2}</li>
          <li>{t.principle3}</li>
          <li>{t.principle4}</li>
        </ul>
      </section>
    </>
  );
}
