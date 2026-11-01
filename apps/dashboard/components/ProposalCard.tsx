"use client";

import { useState } from "react";
import { formatDate, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { Lang, Proposal } from "@/lib/types";

interface Props {
  proposal: Proposal;
  explanation: string;
  lang: Lang;
  t: Strings;
  /** Lifted approval state (shared with the Orders tab). Falls back to local state. */
  approved?: boolean;
  onApprove?: () => void;
}

/** Order proposal with a human approval step. Nothing is ordered in demo mode. */
export function ProposalCard({ proposal: p, explanation, lang, t, approved: approvedProp, onApprove }: Props) {
  const [local, setLocal] = useState(false);
  const approved = approvedProp ?? local;
  const n = (v: number) => `${formatNumber(v, lang)} ${t.units}`;
  const rows: [string, string][] = [
    [t.usable, n(p.usable_stock_units)],
    [t.expiring, n(p.expiring_stock_units)],
    [t.target, n(p.target_stock_units)],
    [t.arrival, formatDate(p.arrival_date, lang)],
    [t.packs, formatNumber(p.order_multiple, lang)],
    [t.outlookWaste, n(p.outlook_waste_units)],
    [t.outlookLost, n(p.outlook_lost_units)],
  ];
  return (
    <section aria-labelledby="proposal-h" className="card">
      <h2 id="proposal-h">{t.proposalTitle}</h2>
      <p className="notice">{t.aiNotice}</p>
      <p className="big" aria-label={`${t.recommended}: ${n(p.recommended_order_units)}`}>
        <span className="big-label">{t.recommended}</span>
        <span className="big-value">{n(p.recommended_order_units)}</span>
      </p>
      <dl className="facts">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <h3>{t.explanationTitle}</h3>
      <p lang={lang}>{explanation}</p>
      <p className="hint">{t.approveHint}</p>
      <button
        type="button"
        className="btn primary"
        onClick={() => (onApprove ? onApprove() : setLocal(true))}
        disabled={approved}
      >
        {t.approve}
      </button>
      <p role="status" className="status">
        {approved ? t.approved : ""}
      </p>
    </section>
  );
}
