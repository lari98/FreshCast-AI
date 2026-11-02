"use client";

import { useContext, useState } from "react";
import type { ReactNode } from "react";
import type { Strings } from "@/lib/i18n";
import { EcoContext } from "./EcoContext";

interface Props<T> {
  rows: T[];
  render: (row: T) => ReactNode;
  /** Number of table columns, so the "show more" row spans the whole table. */
  colSpan: number;
  t: Strings;
  size?: number;
}

/**
 * Table body rows in pages. A chain with hundreds of series would otherwise put
 * thousands of DOM nodes on the page for every tab switch (measured: 400 ms for
 * 336 items). Exports and totals still use every row; only the display is paged.
 */
export function PagedRows<T>({ rows, render, colSpan, t, size: sizeProp }: Props<T>) {
  // Energy-saving mode shows fewer rows at a time, so less is drawn and less memory is used.
  const eco = useContext(EcoContext);
  const size = sizeProp ?? (eco ? 25 : 100);
  const [shown, setShown] = useState(size);
  const left = rows.length - shown;
  return (
    <>
      {rows.slice(0, shown).map(render)}
      {left > 0 && (
        <tr>
          <td colSpan={colSpan}>
            <button type="button" className="btn" onClick={() => setShown((n) => n + size)}>
              {t.showMore} ({left})
            </button>
          </td>
        </tr>
      )}
    </>
  );
}
