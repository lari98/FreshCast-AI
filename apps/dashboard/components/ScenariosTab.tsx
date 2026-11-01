"use client";

import { useState } from "react";
import { formatCurrency, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { COST_SHARE } from "@/lib/kpi";
import { NEUTRAL, ruleOrder } from "@/lib/whatif";
import type { Scenario } from "@/lib/whatif";
import type { Item, Lang } from "@/lib/types";

interface Props {
  item: Item;
  scope: Item[];
  lang: Lang;
  t: Strings;
  costShare?: number;
}

export function ScenariosTab({ item, scope, lang, t, costShare = COST_SHARE }: Props) {
  const [s, setS] = useState<Scenario>(NEUTRAL);
  const n = (v: number) => formatNumber(v, lang);
  const base = ruleOrder(item.proposal);
  const now = ruleOrder(item.proposal, s);
  const planner = item.proposal.recommended_order_units;
  const delta = now - base;

  const scopeCost = { EUR: 0, CHF: 0 };
  const scopeBaseCost = { EUR: 0, CHF: 0 };
  for (const i of scope) {
    const c = i.unit_price * costShare;
    scopeCost[i.currency] += ruleOrder(i.proposal, s) * c;
    scopeBaseCost[i.currency] += ruleOrder(i.proposal) * c;
  }

  return (
    <section aria-labelledby="scen-h" className="card">
      <h2 id="scen-h">{t.scenTitle}</h2>
      <p className="hint">{t.scenHint}</p>
      <p><strong>{t.scenItem}:</strong> {item.name[lang]} · {item.store_id}</p>
      <div className="sliders">
        <label>
          {t.demandChange}: <strong>{s.demandChange > 0 ? "+" : ""}{Math.round(s.demandChange * 100)} %</strong>
          <input
            type="range"
            min={-50}
            max={100}
            step={5}
            value={Math.round(s.demandChange * 100)}
            onChange={(e) => setS({ ...s, demandChange: Number(e.target.value) / 100 })}
          />
        </label>
        <label>
          {t.safetyFactor}: <strong>×{s.safetyFactor.toFixed(1)}</strong>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={s.safetyFactor}
            onChange={(e) => setS({ ...s, safetyFactor: Number(e.target.value) })}
          />
        </label>
        <button type="button" className="btn" onClick={() => setS(NEUTRAL)}>{t.reset}</button>
      </div>

      <dl className="facts">
        <div><dt>{t.baselineRule}</dt><dd>{n(base)} {t.units}</dd></div>
        <div><dt>{t.ruleOrder}</dt><dd><strong>{n(now)} {t.units}</strong></dd></div>
        <div><dt>{t.deltaUnits}</dt><dd>{delta > 0 ? "+" : ""}{n(delta)} {t.units}</dd></div>
        <div><dt>{t.plannerOrder}</dt><dd>{n(planner)} {t.units}</dd></div>
      </dl>

      <h3>{t.scopeTotal}</h3>
      <dl className="facts">
        {(["EUR", "CHF"] as const)
          .filter((c) => scopeBaseCost[c] > 0 || scopeCost[c] > 0)
          .map((c) => (
            <div key={c}>
              <dt>{c}</dt>
              <dd>
                {formatCurrency(scopeBaseCost[c], c, lang)} → <strong>{formatCurrency(scopeCost[c], c, lang)}</strong>
              </dd>
            </div>
          ))}
      </dl>
    </section>
  );
}
