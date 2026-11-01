"use client";

import { useState } from "react";
import { formatCurrency, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { answer, route } from "@/lib/assistant";
import type { Answer, QuestionId } from "@/lib/assistant";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

interface Props {
  metrics: ItemMetrics[];
  lang: Lang;
  t: Strings;
  onOpen: (key: string) => void;
}

const IDS: QuestionId[] = ["attention", "order", "expiry", "stockout", "waste"];

export function AssistantTab({ metrics, lang, t, onOpen }: Props) {
  const [text, setText] = useState("");
  const [asked, setAsked] = useState<{ q: string; id: QuestionId | null } | null>(null);

  const label: Record<QuestionId, string> = {
    attention: t.qAttention, order: t.qOrder, expiry: t.qExpiry, stockout: t.qStockout, waste: t.qWaste,
  };
  const intro: Record<QuestionId, string> = {
    attention: t.aAttention, order: t.aOrder, expiry: t.aExpiry, stockout: t.aStockout, waste: t.aWaste,
  };
  const result: Answer | null = asked?.id ? answer(asked.id, metrics) : null;
  const byKey = new Map(metrics.map((m) => [m.key, m]));

  const ask = (q: string, id: QuestionId | null) => setAsked({ q, id });

  return (
    <section aria-labelledby="assist-h" className="card">
      <h2 id="assist-h">{t.assistTitle}</h2>
      <p className="notice">{t.assistNotice}</p>
      <div className="row">
        {IDS.map((id) => (
          <button key={id} type="button" className="btn" onClick={() => ask(label[id], id)}>
            {label[id]}
          </button>
        ))}
      </div>
      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) ask(text.trim(), route(text));
        }}
      >
        <label>
          {t.ask}
          <input
            type="text"
            value={text}
            placeholder={t.askPlaceholder}
            onChange={(e) => setText(e.target.value)}
            maxLength={200}
          />
        </label>
        <button type="submit" className="btn primary">{t.ask}</button>
      </form>
      <div role="status" aria-live="polite" className="answer">
        {asked && (
          <>
            <p className="q"><strong>{asked.q}</strong></p>
            {!asked.id && <p>{t.aUnknown}</p>}
            {result && result.lines.length === 0 && <p>{t.aNone}</p>}
            {result && result.lines.length > 0 && (
              <>
                <p>{intro[result.id]}</p>
                <ol className="rank">
                  {result.lines.map((l) => {
                    const m = byKey.get(l.key);
                    if (!m) return null;
                    return (
                      <li key={l.key}>
                        <button type="button" className="link" onClick={() => onOpen(l.key)}>
                          {m.item.name[lang]} <span className="muted">· {m.item.store_id}</span>
                        </button>
                        <span>
                          {l.currency === "units"
                            ? `${formatNumber(l.value, lang)} ${t.units}`
                            : formatCurrency(l.value, l.currency, lang)}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
