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
 *
 * Cheap by design: one small conditional request every few minutes, none while the
 * tab is hidden or the computer is offline, and exponential back-off after errors.
 */
export function UpdateWatcher({
  t,
  busy,
  intervalMs = 5 * 60_000,
  fetchImpl,
  reload = () => window.location.reload(),
}: Props) {
  const baseline = useRef<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    let failures = 0;
    let lastCheck = 0;

    // Waits longer after each failure (x2, at most 30 minutes) so a down server is not hammered.
    const delay = () => Math.min(intervalMs * 2 ** failures, 30 * 60_000);
    const schedule = () => {
      window.clearTimeout(timer);
      // A hidden tab does no work at all; the visibilitychange handler resumes it.
      if (!stopped && document.visibilityState !== "hidden") timer = window.setTimeout(tick, delay());
    };
    async function check(): Promise<boolean> {
      lastCheck = Date.now();
      try {
        const f = fetchImpl ?? fetch;
        // "no-cache" revalidates with the ETag: an unchanged file costs a 304 with no body.
        const r = await f("/version.json", { cache: "no-cache" });
        if (!r.ok) return false;
        const { build } = (await r.json()) as { build?: unknown };
        if (typeof build !== "string") return true;
        if (baseline.current === null) baseline.current = build;
        else if (build !== baseline.current && !stopped) setStale(true);
        return true;
      } catch {
        return false; // offline, blocked or no version file (local dev): nothing to do
      }
    }
    async function tick() {
      if (navigator.onLine === false) {
        schedule(); // offline: no request, look again later
        return;
      }
      failures = (await check()) ? 0 : failures + 1;
      schedule();
    }
    const onVisible = () => {
      if (document.visibilityState === "hidden") {
        window.clearTimeout(timer);
      } else if (Date.now() - lastCheck >= intervalMs) {
        void tick();
      } else {
        schedule();
      }
    };
    void tick();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
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
