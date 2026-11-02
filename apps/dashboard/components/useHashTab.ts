"use client";

import { useCallback, useEffect, useState } from "react";
import { tabFromHash } from "@/lib/tabs";
import type { TabId } from "@/lib/tabs";

/** Current tab, kept in sync with the URL hash so a tab can be bookmarked or shared. */
export function useHashTab(): [TabId, (id: string) => void] {
  const [tab, setTab] = useState<TabId>("today");
  useEffect(() => {
    const onHash = () => {
      try {
        setTab(tabFromHash(window.location.hash));
      } catch {
        setTab("today");
      }
    };
    queueMicrotask(onHash); // read the initial hash after hydration
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const change = useCallback((id: string) => {
    setTab(tabFromHash(id));
    try {
      window.history.replaceState(null, "", `#${id}`);
    } catch {
      /* Some embedded viewers forbid history changes; the tab still switches. */
    }
  }, []);
  return [tab, change];
}
