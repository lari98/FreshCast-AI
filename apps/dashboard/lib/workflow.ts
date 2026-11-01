/**
 * Order workflow with the four-eyes principle (demo).
 *
 * planner:  can change a quantity (with a reason) and submit it.
 * reviewer: can approve or reject submitted orders, never their own draft.
 * Switching the role in the UI is NOT authentication; a deployed system needs
 * real sign-in and server-side checks (planned, see docs).
 */

export type Role = "planner" | "reviewer";
export type Status = "draft" | "submitted" | "approved" | "rejected";
export const REASONS = ["promo", "weather", "event", "quality", "supplier", "other"] as const;
export type Reason = (typeof REASONS)[number];

export interface Entry {
  proposed: number;
  qty: number;
  packSize: number;
  reason?: Reason;
  status: Status;
}

export type Workflow = Record<string, Entry>;

const roundToPack = (qty: number, pack: number) =>
  Math.max(0, Math.round(Math.max(0, qty) / pack) * pack);

export function ensure(wf: Workflow, key: string, proposed: number, packSize: number): Entry {
  return wf[key] ?? { proposed, qty: proposed, packSize, status: "draft" };
}

/** Change the quantity (rounded to whole packs). Resets a rejected/approved entry to draft. */
export function setQuantity(
  wf: Workflow, key: string, proposed: number, packSize: number, qty: number,
): Workflow {
  const entry = ensure(wf, key, proposed, packSize);
  const next = roundToPack(qty, packSize);
  return {
    ...wf,
    [key]: {
      ...entry,
      qty: next,
      status: "draft",
      reason: next === entry.proposed ? undefined : entry.reason,
    },
  };
}

export function setReason(wf: Workflow, key: string, reason: Reason | undefined): Workflow {
  const entry = wf[key];
  return entry ? { ...wf, [key]: { ...entry, reason } } : wf;
}

export const isOverride = (e: Entry) => e.qty !== e.proposed;
/** A changed quantity needs a reason before it can be submitted. */
export const canSubmit = (e: Entry) =>
  (e.status === "draft" || e.status === "rejected") && (!isOverride(e) || !!e.reason);

export function submit(
  wf: Workflow, keys: string[], lookup: (key: string) => { proposed: number; packSize: number },
): Workflow {
  const out = { ...wf };
  for (const key of keys) {
    const { proposed, packSize } = lookup(key);
    const entry = ensure(out, key, proposed, packSize);
    if (canSubmit(entry)) out[key] = { ...entry, status: "submitted" };
  }
  return out;
}

export function decide(wf: Workflow, keys: string[], role: Role, approve: boolean): Workflow {
  if (role !== "reviewer") return wf; // four eyes: the person who prepared it cannot approve it
  const out = { ...wf };
  for (const key of keys) {
    const entry = out[key];
    if (entry?.status === "submitted") out[key] = { ...entry, status: approve ? "approved" : "rejected" };
  }
  return out;
}

export function isStatus(wf: Workflow, key: string, status: Status): boolean {
  return wf[key]?.status === status;
}

export function parseWorkflow(raw: unknown): Workflow {
  if (!raw || typeof raw !== "object") return {};
  const out: Workflow = {};
  for (const [key, v] of Object.entries(raw as Record<string, unknown>)) {
    const e = v as Partial<Entry>;
    if (
      typeof e.proposed === "number" && typeof e.qty === "number" && typeof e.packSize === "number" &&
      e.packSize > 0 && ["draft", "submitted", "approved", "rejected"].includes(String(e.status))
    ) {
      out[key] = {
        proposed: e.proposed, qty: e.qty, packSize: e.packSize, status: e.status as Status,
        reason: (REASONS as readonly string[]).includes(String(e.reason)) ? (e.reason as Reason) : undefined,
      };
    }
  }
  return out;
}
