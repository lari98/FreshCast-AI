"use client";

import { useMemo, useState } from "react";
import { formatCurrency, formatNumber } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { ItemMetrics } from "@/lib/kpi";
import type { Lang } from "@/lib/types";

type SortKey = "store" | "product" | "order" | "value" | "waste" | "lost" | "risk";
const RISK_RANK = { low: 0, medium: 1, high: 2 } as const;

interface Props {
  metrics: ItemMetrics[];
  approved: ReadonlySet<string>;
  onApprove: (keys: string[]) => void;
  onOpen: (key: string) => void;
  lang: Lang;
  t: Strings;
}

function sortValue(m: ItemMetrics, key: SortKey, lang: Lang): number | string {
  switch (key) {
    case "store": return m.item.store_id;
    case "product": return m.item.name[lang];
    case "order": return m.orderUnits;
    case "value": return m.orderCost;
    case "waste": return m.item.proposal.outlook_waste_units;
    case "lost": return m.item.proposal.outlook_lost_units;
    case "risk": return RISK_RANK[m.worstRisk];
  }
}

/** Escape a cell for CSV and neutralise spreadsheet formulas (CSV injection). */
export function csvCell(value: string | number): string {
  const text = String(value);
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return /[";\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function OrdersTab({ metrics, approved, onApprove, onOpen, lang, t }: Props) {
  const [query, setQuery] = useState("");
  const [onlyOrder, setOnlyOrder] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "value", dir: "desc" });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = metrics.filter(
      (m) =>
        (!onlyOrder || m.orderUnits > 0) &&
        (!q || `${m.item.name[lang]} ${m.item.sku} ${m.item.store_id}`.toLowerCase().includes(q)),
    );
    const sign = sort.dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const x = sortValue(a, sort.key, lang);
      const y = sortValue(b, sort.key, lang);
      return (typeof x === "string" ? x.localeCompare(String(y)) : x - Number(y)) * sign;
    });
  }, [metrics, query, onlyOrder, sort, lang]);

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const allVisible = rows.length > 0 && rows.every((r) => selected.has(r.key));

  function header(key: SortKey, label: string) {
    const active = sort.key === key;
    return (
      <th scope="col" aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
        <button
          type="button"
          className="sort"
          onClick={() => setSort({ key, dir: active && sort.dir === "desc" ? "asc" : "desc" })}
        >
          {label}
          <span aria-hidden="true">{active ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</span>
        </button>
      </th>
    );
  }

  function exportCsv() {
    const header = ["store_id", "sku", "product", "order_units", "arrival_date", "currency", "order_cost"];
    const lines = [header.join(";")];
    for (const m of metrics.filter((x) => approved.has(x.key))) {
      lines.push(
        [m.item.store_id, m.item.sku, m.item.name[lang], m.orderUnits, m.item.proposal.arrival_date,
          m.item.currency, m.orderCost.toFixed(2)].map(csvCell).join(";"),
      );
    }
    try {
      const url = URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "freshcast-orders.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* Downloads can be blocked in embedded viewers; nothing else to do. */
    }
  }

  const approvedCount = metrics.filter((m) => approved.has(m.key)).length;

  return (
    <section aria-labelledby="orders-h" className="card">
      <h2 id="orders-h">{t.ordersTitle}</h2>
      <p className="hint">{t.ordersHint}</p>
      <div className="toolbar">
        <label>
          {t.search}
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={onlyOrder} onChange={(e) => setOnlyOrder(e.target.checked)} />
          {t.onlyToOrder}
        </label>
        <button
          type="button"
          className="btn primary"
          disabled={selected.size === 0}
          onClick={() => {
            onApprove([...selected]);
            setSelected(new Set());
          }}
        >
          {t.approveSelected} ({selected.size})
        </button>
        <button type="button" className="btn" disabled={approvedCount === 0} onClick={exportCsv}>
          {t.exportCsv} ({approvedCount})
        </button>
      </div>
      <div className="scroll" tabIndex={0} role="region" aria-label={`${t.ordersTitle} – ${t.tableLabel}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">
                <input
                  type="checkbox"
                  aria-label={t.selectAll}
                  checked={allVisible}
                  onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((r) => r.key)) : new Set())}
                />
              </th>
              {header("store", t.colStore)}
              {header("product", t.colProduct)}
              {header("order", t.colOrder)}
              {header("value", t.colValue)}
              {header("waste", t.colWaste)}
              {header("lost", t.colLost)}
              {header("risk", t.risk)}
              <th scope="col">{t.colStatus}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.key}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`${t.selectRow}: ${m.item.name[lang]}, ${m.item.store_id}`}
                    checked={selected.has(m.key)}
                    onChange={() => toggle(m.key)}
                  />
                </td>
                <td>{m.item.store_id}</td>
                <th scope="row">
                  <button type="button" className="link" onClick={() => onOpen(m.key)}>
                    {m.item.name[lang]}
                  </button>
                </th>
                <td>{formatNumber(m.orderUnits, lang)}</td>
                <td>{formatCurrency(m.orderCost, m.item.currency, lang)}</td>
                <td>{formatNumber(m.item.proposal.outlook_waste_units, lang)}</td>
                <td>{formatNumber(m.item.proposal.outlook_lost_units, lang)}</td>
                <td className={`risk risk-${m.worstRisk}`}>{t.risks[m.worstRisk]}</td>
                <td>{approved.has(m.key) ? `✓ ${t.statusApproved}` : t.statusOpen}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p>{t.noItems}</p>}
    </section>
  );
}
