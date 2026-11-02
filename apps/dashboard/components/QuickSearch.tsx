"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Strings } from "@/lib/i18n";

export interface SearchEntry {
  id: string;
  kind: "tab" | "item";
  label: string;
  sub?: string;
}

interface Props {
  entries: SearchEntry[];
  onPick: (entry: SearchEntry) => void;
  onClose: () => void;
  t: Strings;
}

const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

/** Rank: starts-with beats contains; tabs come before items on a tie. */
export function searchEntries(entries: SearchEntry[], query: string, limit = 8): SearchEntry[] {
  const q = norm(query.trim());
  if (!q) return entries.filter((e) => e.kind === "tab").slice(0, limit);
  const scored: { e: SearchEntry; score: number }[] = [];
  for (const e of entries) {
    const label = norm(e.label);
    const hay = `${label} ${norm(e.sub ?? "")}`;
    if (!hay.includes(q)) continue;
    scored.push({ e, score: (label.startsWith(q) ? 0 : label.includes(q) ? 1 : 2) + (e.kind === "tab" ? 0 : 0.5) });
  }
  return scored.sort((a, b) => a.score - b.score).slice(0, limit).map((s) => s.e);
}

/** Ctrl+K dialog: jump to a tab or open an item's forecast. Keyboard only works end to end. */
export function QuickSearch({ entries, onPick, onClose, t }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const results = useMemo(() => searchEntries(entries, query), [entries, query]);

  useEffect(() => input.current?.focus(), []);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); onPick(results[active]!); }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={t.searchTitle} className="palette" onKeyDown={onKey}>
        <input
          ref={input}
          type="search"
          role="combobox"
          aria-expanded="true"
          aria-controls="search-results"
          aria-activedescendant={results[active] ? `sr-${results[active]!.kind}-${results[active]!.id}` : undefined}
          aria-label={t.searchTitle}
          placeholder={t.searchPlaceholder}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActive(0); }}
        />
        <ul id="search-results" role="listbox" aria-label={t.searchTitle}>
          {results.length === 0 && <li className="muted" role="presentation">{t.searchNone}</li>}
          {results.map((r, i) => (
            <li
              key={`${r.kind}-${r.id}`}
              id={`sr-${r.kind}-${r.id}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "on" : ""}
              onMouseEnter={() => setActive(i)}
              onClick={() => onPick(r)}
            >
              <span className="tag">{r.kind === "tab" ? t.searchTab : t.searchItem}</span> {r.label}
              {r.sub && <span className="muted"> · {r.sub}</span>}
            </li>
          ))}
        </ul>
        <p className="hint">{t.searchHint}</p>
      </div>
    </div>
  );
}
