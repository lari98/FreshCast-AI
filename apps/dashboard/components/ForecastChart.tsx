"use client";

import { useId, useState } from "react";
import { formatDate, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { Lang, SeriesPoint } from "@/lib/types";

const W = 720;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 32, left: 44 };

interface Props {
  series: SeriesPoint[];
  lang: Lang;
  t: Strings;
  asOf: string;
}

/**
 * Accessible forecast chart: an SVG with a text alternative and a data table.
 * Actual = solid line, forecast = dashed line, so colour is never the only cue.
 */
export function ForecastChart({ series, lang, t, asOf }: Props) {
  const [asTable, setAsTable] = useState(false);
  const titleId = useId();
  const descId = useId();

  const max = Math.max(1, ...series.map((p) => p.upper), ...series.map((p) => p.actual ?? 0));
  const x = (i: number) =>
    PAD.left + (i * (W - PAD.left - PAD.right)) / Math.max(1, series.length - 1);
  const y = (v: number) => PAD.top + (1 - v / max) * (H - PAD.top - PAD.bottom);

  const line = (pick: (p: SeriesPoint) => number | null) =>
    series
      .map((p, i) => ({ v: pick(p), i }))
      .filter((d): d is { v: number; i: number } => d.v !== null)
      .map((d, k) => `${k === 0 ? "M" : "L"}${x(d.i).toFixed(1)},${y(d.v).toFixed(1)}`)
      .join(" ");

  const band =
    series.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.upper).toFixed(1)}`).join(" ") +
    " " +
    [...series]
      .reverse()
      .map((p, k) => `L${x(series.length - 1 - k).toFixed(1)},${y(p.lower).toFixed(1)}`)
      .join(" ") +
    " Z";

  const asOfIndex = series.findIndex((p) => p.date > asOf);
  const ticks = [0, 0.5, 1].map((f) => Math.round(max * f));

  return (
    <section aria-labelledby={`${titleId}-h`} className="card">
      <div className="card-head">
        <h2 id={`${titleId}-h`}>{t.chartTitle}</h2>
        <button type="button" className="btn" onClick={() => setAsTable((v) => !v)}>
          {asTable ? t.chartToggle : t.tableToggle}
        </button>
      </div>

      {asTable ? (
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.chartTitle} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.date}</th>
                <th scope="col">{t.actual}</th>
                <th scope="col">{t.forecast}</th>
                <th scope="col">{t.lower}</th>
                <th scope="col">{t.upper}</th>
              </tr>
            </thead>
            <tbody>
              {series.map((p) => (
                <tr key={p.date}>
                  <th scope="row">
                    {formatDate(p.date, lang)}
                    {p.is_open ? "" : ` (${t.closed})`}
                  </th>
                  <td>{p.actual === null ? "–" : formatNumber(p.actual, lang)}</td>
                  <td>{formatNumber(p.point, lang, 1)}</td>
                  <td>{formatNumber(p.lower, lang, 1)}</td>
                  <td>{formatNumber(p.upper, lang, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-labelledby={`${titleId} ${descId}`}
          className="chart"
        >
          <title id={titleId}>{t.chartTitle}</title>
          <desc id={descId}>{t.chartDesc}</desc>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} className="grid" />
              <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="axis">
                {formatNumber(tick, lang)}
              </text>
            </g>
          ))}
          <path d={band} className="band" />
          {asOfIndex > 0 && (
            <line
              x1={x(asOfIndex) - (x(1) - x(0)) / 2}
              x2={x(asOfIndex) - (x(1) - x(0)) / 2}
              y1={PAD.top}
              y2={H - PAD.bottom}
              className="today"
            />
          )}
          <path d={line((p) => p.point)} className="forecast" fill="none" />
          <path d={line((p) => p.actual)} className="actual" fill="none" />
          {[0, Math.floor((series.length - 1) / 2), series.length - 1].map((i) => (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" className="axis">
              {series[i] ? formatDate(series[i].date, lang) : ""}
            </text>
          ))}
        </svg>
      )}
      <ul className="legend" aria-hidden="true">
        <li><span className="swatch actual-sw" /> {t.actual}</li>
        <li><span className="swatch forecast-sw" /> {t.forecast}</li>
        <li><span className="swatch band-sw" /> {t.lower}–{t.upper}</li>
      </ul>
    </section>
  );
}
