import type { Strings } from "@/lib/i18n";
import type { Currency } from "@/lib/markets";
import type { OfflineState } from "./useOffline";

export type Theme = "auto" | "light" | "dark";

interface Props {
  costShare: number;
  onCost: (v: number) => void;
  theme: Theme;
  onTheme: (v: Theme) => void;
  onReset: () => void;
  eco: boolean;
  onEco: (v: boolean) => void;
  offline: OfflineState;
  onOfflineReset: () => void;
  t: Strings;
  markets: string[]; // available in the data
  selectedMarkets: ReadonlySet<string>;
  onToggleMarket: (m: string) => void;
  chains: string[];
  selectedChains: ReadonlySet<string>;
  onToggleChain: (c: string) => void;
  currencies: Currency[];
  selectedCurrencies: ReadonlySet<string>;
  onToggleCurrency: (c: string) => void;
}

export function SettingsTab({
  costShare, onCost, theme, onTheme, onReset, eco, onEco, offline, onOfflineReset, t,
  markets, selectedMarkets, onToggleMarket, chains, selectedChains, onToggleChain, currencies, selectedCurrencies, onToggleCurrency,
}: Props) {
  return (
    <>
    <section aria-labelledby="mk-h" className="card">
      <h2 id="mk-h">{t.marketsTitle}</h2>
      <p className="hint">{t.marketsHint}</p>
      <fieldset className="checks">
        <legend>{t.marketLabel}</legend>
        {markets.map((m) => (
          <label key={m} className="check">
            <input type="checkbox" checked={selectedMarkets.has(m)} onChange={() => onToggleMarket(m)} />
            {t.marketNames[m] ?? m}
          </label>
        ))}
      </fieldset>
      {chains.length > 0 && (
        <fieldset className="checks">
          <legend>{t.chainsLabel}</legend>
          {chains.map((c) => (
            <label key={c} className="check">
              <input type="checkbox" checked={selectedChains.has(c)} onChange={() => onToggleChain(c)} />
              {c}
            </label>
          ))}
        </fieldset>
      )}
      <fieldset className="checks">
        <legend>{t.marketsCurrencies}</legend>
        {currencies.map((c) => (
          <label key={c} className="check">
            <input type="checkbox" checked={selectedCurrencies.has(c)} onChange={() => onToggleCurrency(c)} />
            {c}
          </label>
        ))}
      </fieldset>
    </section>
    <section aria-labelledby="set-h" className="card">
      <h2 id="set-h">{t.settingsTitle}</h2>
      <div className="sliders">
        <label>
          {t.settingsCost}: <strong>{Math.round(costShare * 100)} %</strong>
          <input type="range" min={40} max={80} step={5} value={Math.round(costShare * 100)}
            onChange={(e) => onCost(Number(e.target.value) / 100)} />
        </label>
        <p className="hint">{t.settingsCostHint}</p>
        <label>
          {t.theme}
          <select value={theme} onChange={(e) => onTheme(e.target.value as Theme)}>
            <option value="auto">{t.themeAuto}</option>
            <option value="light">{t.themeLight}</option>
            <option value="dark">{t.themeDark}</option>
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={eco} onChange={(e) => onEco(e.target.checked)} />
          {t.ecoLabel}
        </label>
        <p className="hint">{t.ecoHint}</p>
        <button type="button" className="btn" onClick={onReset}>{t.resetSettings}</button>
        <p className="hint">{t.settingsSaved}</p>
      </div>
    </section>
    <section aria-labelledby="off-h" className="card">
      <h2 id="off-h">{t.offlineTitle}</h2>
      <p className="hint">{t.offlineHint}</p>
      <p role="status">
        {{ ready: t.offlineReady, pending: t.offlinePending, off: t.offlineOff, unsupported: t.offlineUnsupported }[offline]}
      </p>
      {offline === "ready" && (
        <button type="button" className="btn" onClick={onOfflineReset}>{t.offlineReset}</button>
      )}
    </section>
    </>
  );
}
