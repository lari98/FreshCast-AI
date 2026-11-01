import { formatDate, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { Lang, Quality } from "@/lib/types";

interface Props {
  quality: Quality;
  lang: Lang;
  t: Strings;
}

/** Shows what the API found and repaired in the upload. */
export function QualityPanel({ quality: q, lang, t }: Props) {
  return (
    <section aria-labelledby="quality-h" className="card">
      <h2 id="quality-h">{t.qualityTitle}</h2>
      <dl className="facts">
        <div><dt>{t.qualityRows}</dt><dd>{formatNumber(q.rows_used, lang)}</dd></div>
        <div><dt>{t.qualitySeries}</dt><dd>{formatNumber(q.series_used, lang)}</dd></div>
        <div>
          <dt>{t.qualityPeriod}</dt>
          <dd>{formatDate(q.date_from, lang)} – {formatDate(q.date_to, lang)}</dd>
        </div>
        <div><dt>{t.qualityCalibrated}</dt><dd>{q.calibrated ? t.yes : t.no}</dd></div>
      </dl>
      {q.warnings.length > 0 && (
        <>
          <h3>{t.warnings}</h3>
          <ul>{q.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </>
      )}
      {q.skipped.length > 0 && (
        <>
          <h3>{t.skipped}</h3>
          <ul>{q.skipped.map((w) => <li key={w}>{w}</li>)}</ul>
        </>
      )}
    </section>
  );
}
