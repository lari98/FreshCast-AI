import { formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { AuditEvent } from "@/lib/audit";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

interface Props {
  events: AuditEvent[];
  metrics: ItemMetrics[];
  lang: Lang;
  t: Strings;
}

const SHOWN = 20;

/** Who did what to which order, newest first (this browser only; see lib/audit.ts). */
export function AuditPanel({ events, metrics, lang, t }: Props) {
  const name = (key: string) => metrics.find((m) => m.key === key)?.item.name[lang] ?? key;
  const when = (iso: string) =>
    new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", { dateStyle: "short", timeStyle: "short" }).format(new Date(iso));
  const action = { submitted: t.statusSubmitted, approved: t.statusApproved, rejected: t.statusRejected };
  return (
    <section aria-labelledby="audit-h" className="card">
      <h2 id="audit-h">{t.auditTitle}</h2>
      <p className="hint">{t.auditHint}</p>
      {events.length === 0 ? (
        <p>{t.auditEmpty}</p>
      ) : (
        <div className="scroll" tabIndex={0} role="region" aria-label={`${t.auditTitle} – ${t.tableLabel}`}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colWhen}</th>
                <th scope="col">{t.colRole}</th>
                <th scope="col">{t.colDoing}</th>
                <th scope="col">{t.colProduct}</th>
                <th scope="col">{t.colProposed}</th>
                <th scope="col">{t.colFinal}</th>
                <th scope="col">{t.colReason}</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, SHOWN).map((e, i) => (
                <tr key={`${e.at}-${e.key}-${i}`}>
                  <td className="nowrap">{when(e.at)}</td>
                  <td>{e.role === "planner" ? t.rolePlanner : t.roleReviewer}</td>
                  <td>{action[e.action]}</td>
                  <th scope="row">{name(e.key)} <span className="muted">{e.key.split("|")[0]}</span></th>
                  <td>{formatNumber(e.proposed, lang)}</td>
                  <td>{formatNumber(e.qty, lang)}</td>
                  <td>{e.reason ? t.reasons[e.reason] : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
