import type { Strings } from "@/lib/i18n";

export type Theme = "auto" | "light" | "dark";

interface Props {
  costShare: number;
  onCost: (v: number) => void;
  theme: Theme;
  onTheme: (v: Theme) => void;
  onReset: () => void;
  t: Strings;
}

export function SettingsTab({ costShare, onCost, theme, onTheme, onReset, t }: Props) {
  return (
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
        <button type="button" className="btn" onClick={onReset}>{t.resetSettings}</button>
        <p className="hint">{t.settingsSaved}</p>
      </div>
    </section>
  );
}
