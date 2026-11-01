import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { POLICY_IDS, change } from "@/lib/replay";
import type { PolicyId, Replay } from "@/lib/replay";
import type { Lang } from "@/lib/types";

interface Props {
  replay: Replay | null;
  failed: boolean;
  lang: Lang;
  t: Strings;
}

const signed = (v: number | null, lang: Lang) =>
  v === null ? "–" : `${v > 0 ? "+" : ""}${formatPercent(v, lang, 1)}`;

export function SavingsTab({ replay, failed, lang, t }: Props) {
  if (failed) return <p role="alert">{t.replayError}</p>;
  if (!replay) return <p role="status">{t.loading}</p>;

  const names: Record<PolicyId, string> = {
    naive: t.polNaive, rule_v1: t.polRule, newsvendor: t.polNewsvendor, planner: t.polPlanner,
  };
  const currencies = Object.keys(replay.policies.naive);
  const lead = currencies.includes("EUR") ? "EUR" : (currencies[0] ?? "EUR");
  const nv = replay.policies.newsvendor[lead];
  const rule = replay.policies.rule_v1[lead];
  const { wins, weeks } = replay.newsvendor_beats_rule_v1_weeks;
  const weeklyMax = Math.max(1, ...POLICY_IDS.flatMap((p) => replay.weekly[p].waste));
  const nWeeks = replay.weekly.naive.waste.length;
  const cats = Object.keys(replay.categories).sort();

  const cards: { label: string; value: string; note: string }[] = nv && rule ? [
    { label: t.savProfit, value: signed(nv.profit_vs_naive, lang), note: `${names.newsvendor} ${t.savVs} ${names.naive}` },
    { label: t.savWaste, value: signed(change(nv.waste_cost, rule.waste_cost), lang), note: `${names.newsvendor} ${t.savVs} ${names.rule_v1}` },
    { label: t.savFill, value: formatPercent(nv.fill_rate, lang), note: `${names.rule_v1}: ${formatPercent(rule.fill_rate, lang)}` },
    { label: t.savWeeks, value: `${formatNumber(wins, lang)} ${t.kpiOf} ${formatNumber(weeks, lang)}`, note: `${names.newsvendor} ${t.savVs} ${names.rule_v1}` },
  ] : [];

  return (
    <>
      <p className="banner-box" role="note">{t.savNotice}</p>
      <p className="hint">
        {t.savWindow}: {formatDate(replay.from, lang)} – {formatDate(replay.to, lang)} · {formatNumber(replay.series, lang)} {t.savSeries}
      </p>
      <ul className="kpis">
        {cards.map((c) => (
          <li key={c.label} className="kpi">
            <span className="kpi-label">{c.label}</span>
            <span className="kpi-value">{c.value}</span>
            <span className="kpi-note">{c.note}</span>
          </li>
        ))}
      </ul>

      {currencies.map((cur) => (
        <section key={cur} aria-labelledby={`pol-${cur}`} className="card">
          <h2 id={`pol-${cur}`}>{t.savPolicies} ({cur})</h2>
          <div className="scroll" tabIndex={0} role="region" aria-label={`${t.savPolicies} ${cur} – ${t.tableLabel}`}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t.savPolicy}</th>
                  <th scope="col">{t.savFill}</th>
                  <th scope="col">{t.colWasteRate}</th>
                  <th scope="col">{t.savWasteCol}</th>
                  <th scope="col">{t.savLostCol}</th>
                  <th scope="col">{t.savProfitCol}</th>
                  <th scope="col">{t.savProfit}</th>
                </tr>
              </thead>
              <tbody>
                {POLICY_IDS.map((p) => {
                  const s = replay.policies[p][cur];
                  if (!s) return null;
                  const money = (v: number) => formatCurrency(v, cur as "EUR" | "CHF", lang);
                  return (
                    <tr key={p}>
                      <th scope="row">{names[p]}</th>
                      <td>{formatPercent(s.fill_rate, lang)}</td>
                      <td>{formatPercent(s.waste_rate, lang)}</td>
                      <td>{money(s.waste_cost)}</td>
                      <td>{money(s.lost_margin)}</td>
                      <td>{money(s.profit)}</td>
                      <td>{p === "naive" ? "–" : signed(s.profit_vs_naive, lang)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <section aria-labelledby="wk-h" className="card">
        <h2 id="wk-h">{t.savWeekly}</h2>
        <p className="hint">{t.savWeeklyHint}</p>
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.savWeekly} – ${t.tableLabel}`}>
          <table className="heat">
            <thead>
              <tr>
                <th scope="col">{t.savPolicy}</th>
                {Array.from({ length: nWeeks }, (_, w) => <th key={w} scope="col">{t.savWeekShort}{w + 1}</th>)}
                <th scope="col">{t.colTotal}</th>
              </tr>
            </thead>
            <tbody>
              {POLICY_IDS.map((p) => (
                <tr key={p}>
                  <th scope="row">{names[p]}</th>
                  {replay.weekly[p].waste.map((v, w) => (
                    <td
                      key={w}
                      className="cell"
                      style={{ backgroundColor: `color-mix(in srgb, var(--crit) ${Math.round((v / weeklyMax) * 45)}%, transparent)` }}
                    >
                      {formatNumber(v, lang)}
                    </td>
                  ))}
                  <td><strong>{formatNumber(replay.weekly[p].waste.reduce((a, b) => a + b, 0), lang)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="sc-h" className="card">
        <h2 id="sc-h">{t.savCategories}</h2>
        <p className="hint">{t.savCategoriesHint}</p>
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.savCategories} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colCategory}</th>
                {POLICY_IDS.map((p) => <th key={p} scope="col">{names[p]}</th>)}
              </tr>
            </thead>
            <tbody>
              {cats.map((c) => (
                <tr key={c}>
                  <th scope="row">{t.categoryNames[c] ?? c}</th>
                  {POLICY_IDS.map((p) => {
                    const v = replay.categories[c]?.[p];
                    return (
                      <td key={p}>
                        {v ? `${formatPercent(v.waste_rate, lang)} / ${formatPercent(v.fill_rate, lang)}` : "–"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="how-h" className="card">
        <h2 id="how-h">{t.savHow}</h2>
        <ul>
          <li>{t.savHow1}</li>
          <li>{t.savHow2}</li>
          <li>{t.savHow3}</li>
        </ul>
        <h3>{t.savFactors}</h3>
        <p className="hint">{t.savFactorsHint}</p>
        <dl className="facts">
          {Object.entries(replay.overage_factors).sort().map(([sku, f]) => (
            <div key={sku}><dt>{sku}</dt><dd>{formatNumber(f, lang, 2)}</dd></div>
          ))}
        </dl>
      </section>
    </>
  );
}
