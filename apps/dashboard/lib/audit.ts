import { REASONS } from "./workflow";
import type { Reason, Role, Status, Workflow } from "./workflow";

/**
 * Local audit trail of order decisions. It lives in this browser only, so it is a
 * convenience for the person using the dashboard, not a tamper-proof record: the
 * real audit log is the API's (server side, append-only).
 */
export type AuditAction = "submitted" | "approved" | "rejected";

export interface AuditEvent {
  at: string; // ISO timestamp
  role: Role;
  action: AuditAction;
  key: string;
  qty: number;
  proposed: number;
  reason?: Reason;
}

export const MAX_EVENTS = 200;
const ACTIONS: readonly string[] = ["submitted", "approved", "rejected"];

/** Events for every entry whose status changed between two workflow states. */
export function diffWorkflow(before: Workflow, after: Workflow, role: Role, at: string): AuditEvent[] {
  const events: AuditEvent[] = [];
  for (const [key, entry] of Object.entries(after)) {
    const was: Status = before[key]?.status ?? "draft";
    if (entry.status !== was && ACTIONS.includes(entry.status)) {
      events.push({
        at, role, action: entry.status as AuditAction, key, qty: entry.qty, proposed: entry.proposed,
        ...(entry.reason ? { reason: entry.reason } : {}),
      });
    }
  }
  return events;
}

/** Newest first, capped. */
export function append(log: AuditEvent[], events: AuditEvent[]): AuditEvent[] {
  return [...events, ...log].slice(0, MAX_EVENTS);
}

/** Read the stored log defensively: anything malformed is dropped. */
export function parseAudit(raw: unknown): AuditEvent[] {
  if (!Array.isArray(raw)) return [];
  const out: AuditEvent[] = [];
  for (const e of raw) {
    if (!e || typeof e !== "object") continue;
    const r = e as Record<string, unknown>;
    if (
      typeof r.at === "string" && typeof r.key === "string" && typeof r.qty === "number" &&
      typeof r.proposed === "number" && ACTIONS.includes(r.action as string) &&
      (r.role === "planner" || r.role === "reviewer")
    ) {
      out.push({
        at: r.at, key: r.key, qty: r.qty, proposed: r.proposed, role: r.role, action: r.action as AuditAction,
        ...(REASONS.includes(r.reason as Reason) ? { reason: r.reason as Reason } : {}),
      });
    }
    if (out.length >= MAX_EVENTS) break;
  }
  return out;
}
