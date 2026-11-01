import { formatNumber, formatPercent } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { chainMap } from "@/lib/chainmap";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

interface Props {
  /** Metrics of the whole network (not filtered), so every chain stays visible. */
  metrics: ItemMetrics[];
  markets: string[];
  selectedMarkets: ReadonlySet<string>;
  selectedChains: ReadonlySet<string>;
  /** Show only this chain in this market. */
  onPick: (market: string, chain: string) => void;
  onShowAll: () => void;
  lang: Lang;
  t: Strings;
}

export function MapTab({ metrics, markets, selectedMarkets, selectedChains, onPick, onShowAll, lang, t }: Props) {
  const map = chainMap(metrics, markets);
  if (map.rows.length === 0) return <p>{t.mapNone}</p>;
  const max = Math.max(0.0001, ...map.rows.flatMap((r) => Object.values(r.cells).map((c) => c?.lossRatio ?? 0)));
  return (
    <>
      <section aria-labelledby="map-h" className="card">
        <h2 id="map-h">{t.mapTitle}</h2>
        <p className="hint">{t.mapHint}</p>
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.mapTitle} – ${t.tableLabel}`}>
          <table className="chainmap">
            <thead>
              <tr>
                <th scope="col">{t.chainLabel}</th>
                {map.markets.map((m) => <th key={m} scope="col">{t.marketNames[m] ?? m}</th>)}
                <th scope="col">{t.mapPresence}</th>
              </tr>
            </thead>
            <tbody>
              {map.rows.map((r) => (
                <tr key={r.chain}>
                  <th scope="row">{r.chain}</th>
                  {map.markets.map((m) => {
                    const c = r.cells[m];
                    if (!c) return <td key={m} className="muted">–</td>;
                    const active = selectedMarkets.has(m) && selectedChains.has(r.chain);
                    return (
                      <td key={m} className={active ? "map-cell on" : "map-cell"}>
                        <button
                          type="button"
                          className="cell-btn"
                          aria-pressed={active}
                          aria-label={`${r.chain}, ${t.marketNames[m] ?? m}: ${t.mapOnly}`}
                          onClick={() => onPick(m, r.chain)}
                        >
                          <strong>{formatNumber(c.stores, lang)}</strong> {c.stores === 1 ? t.mapStore : t.mapStores}
                          <span className="muted"> · {formatNumber(c.items, lang)} {t.mapItems}</span>
                          <span className="bar-track" aria-hidden="true">
                            <span className="bar-fill warn" style={{ width: `${((c.lossRatio ?? 0) / max) * 100}%` }} />
                          </span>
                          <span className="muted">{t.colLossRatio}: {formatPercent(c.lossRatio, lang)}</span>
                        </button>
                      </td>
                    );
                  })}
                  <td>
                    {r.countries.length > 1
                      ? `${formatNumber(r.countries.length, lang)} ${t.mapCountries}: ${r.countries.join(" · ")}`
                      : `${t.mapOneCountry}: ${r.countries[0] ?? ""}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className="btn" onClick={onShowAll}>{t.mapShowAll}</button>
      </section>
      <p className="banner-box" role="note">{t.mapFictional}</p>
    </>
  );
}
