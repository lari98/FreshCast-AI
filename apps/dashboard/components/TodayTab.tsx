"use client";

import { useEffect, useState } from "react";
import { formatDate, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import { buildTasks, closures } from "@/lib/today";
import type { TaskId } from "@/lib/today";
import type { ItemMetrics } from "@/lib/kpi";
import type { Item, Lang } from "@/lib/types";
import type { Role, Workflow } from "@/lib/workflow";

interface Props {
  metrics: ItemMetrics[];
  items: Item[];
  workflow: Workflow;
  role: Role;
  asOf: string;
  lang: Lang;
  t: Strings;
  onGo: (tab: string) => void;
}

const KEY = "freshcast.today.v1";

/** Ticked tasks are remembered for the planning day only (a new day starts empty). */
function useDone(asOf: string): [Set<TaskId>, (id: TaskId) => void] {
  const [done, setDone] = useState<Set<TaskId>>(new Set());
  useEffect(() => {
    queueMicrotask(() => {
      try {
        const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "null");
        if (raw?.asOf === asOf && Array.isArray(raw.done)) setDone(new Set(raw.done as TaskId[]));
        else setDone(new Set());
      } catch {
        setDone(new Set());
      }
    });
  }, [asOf]);
  const toggle = (id: TaskId) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        window.localStorage.setItem(KEY, JSON.stringify({ asOf, done: [...next] }));
      } catch {
        /* storage blocked: the ticks last until the page closes */
      }
      return next;
    });
  return [done, toggle];
}

export function TodayTab({ metrics, items, workflow, role, asOf, lang, t, onGo }: Props) {
  const [done, toggle] = useDone(asOf);
  const tasks = buildTasks(metrics, items, workflow, role, asOf);
  const text: Record<TaskId, string> = {
    approve: t.taskApprove, review: t.taskReview, expiry: t.taskExpiry,
    stockout: t.taskStockout, spike: t.taskSpike, closures: t.taskClosures,
  };
  const closed = closures(items);
  const storeCount = new Set(items.map((i) => i.store_id)).size;
  const weekday = (iso: string) =>
    new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", { weekday: "short", timeZone: "UTC" })
      .format(new Date(`${iso}T00:00:00Z`));
  const open = tasks.filter((x) => !done.has(x.id)).length;

  return (
    <>
      <section aria-labelledby="today-h" className="card">
        <h2 id="today-h">{t.todayTitle} · {formatDate(asOf, lang)}</h2>
        <p className="hint">{t.todayIntro}</p>
        {tasks.length === 0 ? (
          <p role="status">✓ {t.taskNone}</p>
        ) : (
          <>
            <p role="status"><strong>{formatNumber(open, lang)}</strong> {t.todayOpen}</p>
            <ul className="tasks">
              {tasks.map((task) => (
                <li key={task.id} className={done.has(task.id) ? "done" : ""}>
                  <label className="check">
                    <input type="checkbox" checked={done.has(task.id)} onChange={() => toggle(task.id)} />
                    <span>
                      <strong>{formatNumber(task.count, lang)}</strong> {text[task.id]}
                    </span>
                  </label>
                  <button type="button" className="btn small" onClick={() => onGo(task.tab)}>{t.taskGo}</button>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section aria-labelledby="clos-h" className="card">
        <h2 id="clos-h">{t.closuresTitle}</h2>
        <p className="hint">{t.closuresHint}</p>
        {closed.length === 0 ? (
          <p>{t.closuresNone}</p>
        ) : (
          <ul className="plain">
            {closed.map((c) => (
              <li key={c.date}>
                <strong>{weekday(c.date)} {formatDate(c.date, lang)}</strong>: {c.stores.length === storeCount
                  ? t.allStores
                  : c.stores.map((s) => `${s.city} (${t.marketNames[s.market] ?? s.market})`).join(", ")}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
