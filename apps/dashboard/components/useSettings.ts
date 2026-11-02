"use client";

import { useEffect, useState } from "react";
import { COST_SHARE } from "@/lib/kpi";
import { parseAudit } from "@/lib/audit";
import type { AuditEvent } from "@/lib/audit";
import { parseWorkflow } from "@/lib/workflow";
import type { Role, Workflow } from "@/lib/workflow";
import type { Theme } from "./SettingsTab";

const STORAGE_KEY = "freshcast.settings.v2";

const strings = (v: unknown): string[] | null =>
  Array.isArray(v) && v.every((x) => typeof x === "string") ? (v as string[]) : null;

/**
 * Everything the user chose that should survive a reload: cost share, theme, role,
 * market / currency / chain filters and the approval workflow. Stored in this
 * browser only (localStorage); reading and writing are wrapped because storage can
 * be blocked. An uploaded data set never persists its workflow.
 */
export function useSettings(isUpload: boolean) {
  const [workflow, setWorkflow] = useState<Workflow>({});
  const [role, setRole] = useState<Role>("planner");
  const [costShare, setCostShare] = useState(COST_SHARE);
  const [theme, setTheme] = useState<Theme>("auto");
  const [restored, setRestored] = useState(false);
  // null = no restriction (everything that exists in the data)
  const [marketSel, setMarketSel] = useState<string[] | null>(null);
  const [currencySel, setCurrencySel] = useState<string[] | null>(null);
  const [chainSel, setChainSel] = useState<string[] | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);

  useEffect(() => {
    queueMicrotask(() => {
      try {
        const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null");
        if (raw && typeof raw === "object") {
          if (typeof raw.costShare === "number" && raw.costShare >= 0.4 && raw.costShare <= 0.8) setCostShare(raw.costShare);
          if (["auto", "light", "dark"].includes(raw.theme)) setTheme(raw.theme);
          if (raw.role === "reviewer" || raw.role === "planner") setRole(raw.role);
          setMarketSel(strings(raw.markets));
          setCurrencySel(strings(raw.currencies));
          setChainSel(strings(raw.chains));
          setWorkflow(parseWorkflow(raw.workflow));
          setAudit(parseAudit(raw.audit));
        }
      } catch {
        /* Storage can be blocked (private window, embedded viewer); start fresh. */
      }
      setRestored(true);
    });
  }, []);

  useEffect(() => {
    if (!restored) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          costShare, theme, role, markets: marketSel, currencies: currencySel, chains: chainSel,
          workflow: isUpload ? {} : workflow,
          audit: isUpload ? [] : audit,
        }),
      );
    } catch {
      /* Not persisted; the page still works. */
    }
  }, [restored, costShare, theme, role, marketSel, currencySel, chainSel, workflow, audit, isUpload]);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);

  return {
    workflow, setWorkflow, role, setRole, costShare, setCostShare, theme, setTheme,
    marketSel, setMarketSel, currencySel, setCurrencySel, chainSel, setChainSel, audit, setAudit,
  };
}
