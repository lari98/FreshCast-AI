"use client";

import { useCallback, useEffect, useState } from "react";

export type OfflineState = "unsupported" | "pending" | "ready" | "off";

/**
 * Registers the service worker (production builds on https or localhost only) and reports
 * whether the dashboard can open offline and whether the browser is online right now.
 * Reset removes the worker and its saved copy; settings and approvals in localStorage stay.
 */
export function useOffline() {
  const [state, setState] = useState<OfflineState>("pending");
  const [online, setOnline] = useState(true);

  useEffect(() => {
    queueMicrotask(() => setOnline(navigator.onLine !== false));
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const sw = typeof navigator !== "undefined" ? navigator.serviceWorker : undefined;
    if (process.env.NODE_ENV !== "production" || !sw) {
      queueMicrotask(() => alive && setState("unsupported"));
      return;
    }
    sw.register("/sw.js", { scope: "/", updateViaCache: "none" })
      .then(() => sw.ready)
      .then(() => alive && setState("ready"))
      .catch(() => alive && setState("unsupported")); // blocked, or not a secure context
    return () => {
      alive = false;
    };
  }, []);

  const reset = useCallback(async () => {
    try {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith("freshcast-")).map((n) => caches.delete(n)));
    } finally {
      setState("off");
    }
  }, []);

  return { state, online, reset };
}
