"use client";

import { useEffect, useRef, useState } from "react";
import type { Strings } from "@/lib/i18n";

interface Props {
  t: Strings;
  /** True while the page holds data that a reload would lose (an uploaded file). */
  busy: boolean;
  intervalMs?: number;
  /** Injected in tests. */
  fetchImpl?: typeof fetch;
  reload?: () => void;
}

/**
 * Notices a newer deployment (public/version.json changes) and loads it without
 * the user closing anything. Settings and the approval workflow live in
 * localStorage, so a reload keeps them; uploaded data does not, so with an
 * upload loaded the user gets a button instead of an automatic reload.
 */
export function UpdateWatcher({
  t,
  busy,
  intervalMs = 60_000,
  fetchImpl,
  reload = () => window.location.reload(),
}: Props) {
  const baseline = useRef<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let stopped = false;
    async function check() {
      try {
        const f = fetchImpl ?? fetch;
        const r = await f("/version.json", { cache: "no-store" });
        if (!r.ok) return;
        const { build } = (await r.json()) as { build?: unknown };
        if (typeof build !== "string") return;
        if (baseline.current === null) baseline.current = build;
        else if (build !== baseline.current && !stopped) setStale(true);
      } catch {
        /* offline, blocked or no version file (local dev): nothing to do */
      }
    }
    void check();
    const timer = window.setInterval(check, intervalMs);
    const onVisible = () => document.visibilityState === "visible" && void check();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [fetchImpl, intervalMs]);

  useEffect(() => {
    if (!stale || busy) return;
    const timer = window.setTimeout(reload, 4000);
    return () => window.clearTimeout(timer);
  }, [stale, busy, reload]);

  if (!stale) return null;
  return (
    <p className="banner-box update" role="status">
      {busy ? t.updateBusy : t.updateReady}{" "}
      <button type="button" className="btn small" onClick={reload}>{t.updateReload}</button>
    </p>
  );
}
