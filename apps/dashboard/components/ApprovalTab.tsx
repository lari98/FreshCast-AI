"use client";

import { AuditPanel } from "./AuditPanel";
import type { AuditEvent } from "@/lib/audit";
import { PagedRows } from "./PagedRows";
import { useState } from "react";
import { formatCurrency, formatMoney, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";
import { REASONS, canSubmit, ensure, isOverride } from "@/lib/workflow";
import type { Reason, Role, Status, Workflow } from "@/lib/workflow";

interface Props {
  metrics: ItemMetrics[];
  workflow: Workflow;
  role: Role;
  costShare: number;
  onRole: (r: Role) => void;
  onQty: (m: ItemMetrics, qty: number) => void;
  onReason: (key: string, reason: Reason | undefined) => void;
  onSubmit: (keys: string[]) => void;
  onDecide: (keys: string[], approve: boolean) => void;
  onOpen: (key: string) => void;
  audit: AuditEvent[];
  lang: Lang;
  t: Strings;
}

/** Number field that commits on blur/Enter and steps by whole packs. */
function QtyInput({ value, pack, label, disabled, onCommit }: {
  value: number; pack: number; label: string; disabled: boolean; onCommit: (v: number) => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const commit = () => {
    if (text !== null && text.trim() !== "" && Number.isFinite(Number(text))) onCommit(Number(text));
    setText(null);
  };
  return (
    <span className="qty">
      <button type="button" className="btn small" aria-label={`${label} −${pack}`} disabled={disabled}
        onClick={() => onCommit(Math.max(0, value - pack))}>−</button>
      <input
        type="number" min={0} step={pack} aria-label={label} disabled={disabled}
        value={text ?? value}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); }}
      />
      <button type="button" className="btn small" aria-label={`${label} +${pack}`} disabled={disabled}
        onClick={() => onCommit(value + pack)}>+</button>
    </span>
  );
}

export function ApprovalTab(p: Props) {
  const { metrics, workflow, role, costShare, lang, t } = p;
  const rows = metrics
    .filter((m) => m.orderUnits > 0 || workflow[m.key])
    .sort((a, b) => b.orderCost - a.orderCost);
  const entry = (m: ItemMetrics) => ensure(workflow, m.key, m.orderUnits, m.item.proposal.order_multiple);
  const statusText: Record<Status, string> = {
    draft: t.statusDraft, submitted: t.statusSubmitted, approved: `✓ ${t.statusApproved}`, rejected: t.statusRejected,
  };
  const unitCost = (m: ItemMetrics) => m.item.unit_price * costShare;

  const approvedValue = { EUR: 0, CHF: 0 };
  let overrides = 0;
  for (const m of rows) {
    const e = entry(m);
    if (isOverride(e)) overrides += 1;
    if (e.status === "approved") approvedValue[m.item.currency] += e.qty * unitCost(m);
  }
  const submitted = rows.filter((m) => entry(m).status === "submitted").map((m) => m.key);
  const drafts = rows.filter((m) => canSubmit(entry(m))).map((m) => m.key);
  const reviewer = role === "reviewer";

  return (
    <>
    <section aria-labelledby="appr-h" className="card">
      <h2 id="appr-h">{t.approvalTitle}</h2>
      <p className="hint">{t.approvalHint}</p>
      <div className="toolbar">
        <label>
          {t.role}
          <select value={role} onChange={(e) => p.onRole(e.target.value as Role)}>
            <option value="planner">{t.rolePlanner}</option>
            <option value="reviewer">{t.roleReviewer}</option>
          </select>
        </label>
        <button type="button" className="btn primary" disabled={reviewer || drafts.length === 0}
          onClick={() => p.onSubmit(drafts)}>{t.submitAll} ({drafts.length})</button>
        <button type="button" className="btn primary" disabled={!reviewer || submitted.length === 0}
          onClick={() => p.onDecide(submitted, true)}>{t.approveAll} ({submitted.length})</button>
        <button type="button" className="btn" disabled={!reviewer || submitted.length === 0}
          onClick={() => p.onDecide(submitted, false)}>{t.rejectAll}</button>
      </div>
      <p role="status" aria-live="polite">
        <strong>{t.approvalSummary}:</strong> {formatMoney(approvedValue, lang)} · <strong>{t.overridesCount}:</strong>{" "}
        {formatNumber(overrides, lang)}
      </p>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.approvalTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t.colProduct}</th>
              <th scope="col">{t.colStore}</th>
              <th scope="col">{t.colProposed}</th>
              <th scope="col">{t.colFinal}</th>
              <th scope="col">{t.colReason}</th>
              <th scope="col">{t.colDelta}</th>
              <th scope="col">{t.colStatus}</th>
              <th scope="col">{t.colAction}</th>
            </tr>
          </thead>
          <tbody>
            <PagedRows rows={rows} colSpan={10} t={t} render={(m) => {
              const e = entry(m);
              const locked = reviewer || e.status === "submitted" || e.status === "approved";
              const delta = (e.qty - e.proposed) * unitCost(m);
              const name = `${m.item.name[lang]}, ${m.item.store_id}`;
              return (
                <tr key={m.key}>
                  <th scope="row">
                    <button type="button" className="link" onClick={() => p.onOpen(m.key)}>{m.item.name[lang]}</button>
                  </th>
                  <td className="nowrap">{m.item.store_id}</td>
                  <td>{formatNumber(e.proposed, lang)}</td>
                  <td>
                    <QtyInput value={e.qty} pack={e.packSize} label={`${t.colFinal}: ${name}`} disabled={locked}
                      onCommit={(v) => p.onQty(m, v)} />
                  </td>
                  <td>
                    <select aria-label={`${t.colReason}: ${name}`} value={e.reason ?? ""} disabled={locked || !isOverride(e)}
                      onChange={(ev) => p.onReason(m.key, (ev.target.value || undefined) as Reason | undefined)}>
                      <option value="">{t.reasonNone}</option>
                      {REASONS.map((r) => <option key={r} value={r}>{t.reasons[r]}</option>)}
                    </select>
                  </td>
                  <td>{isOverride(e) ? formatCurrency(delta, m.item.currency, lang) : "–"}</td>
                  <td>{statusText[e.status]}</td>
                  <td>
                    {e.status === "submitted" && reviewer ? (
                      <span className="row">
                        <button type="button" className="btn small primary" onClick={() => p.onDecide([m.key], true)}>{t.approveOne}</button>
                        <button type="button" className="btn small" onClick={() => p.onDecide([m.key], false)}>{t.rejectOne}</button>
                      </span>
                    ) : canSubmit(e) && !reviewer ? (
                      <button type="button" className="btn small" onClick={() => p.onSubmit([m.key])}>{t.submit}</button>
                    ) : isOverride(e) && !e.reason && !reviewer && (e.status === "draft" || e.status === "rejected") ? (
                      <span className="hint">{t.needReason}</span>
                    ) : null}
                  </td>
                </tr>
              );
            }} />
          </tbody>
        </table>
      </div>
      <p className="hint">{t.fvaNote}</p>
    </section>
    <AuditPanel events={p.audit} metrics={metrics} lang={lang} t={t} />
    </>
  );
}
