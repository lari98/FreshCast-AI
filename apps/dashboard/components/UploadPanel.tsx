"use client";

import { useState } from "react";
import type { Strings } from "@/lib/i18n";
import { UploadError, analyzeUpload } from "@/lib/source";
import type { DashboardData } from "@/lib/types";
import { checkUpload } from "@/lib/uploadGuard";

interface Props {
  t: Strings;
  onData: (data: DashboardData) => void;
  onReset: () => void;
  showReset: boolean;
  /** Injected in tests. */
  upload?: typeof analyzeUpload;
}

/** Upload form: sales CSV (required) and stock CSV (optional). */
export function UploadPanel({ t, onData, onReset, showReset, upload = analyzeUpload }: Props) {
  const [sales, setSales] = useState<File | null>(null);
  const [stock, setStock] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!sales) return;
    setBusy(true);
    setProblems([]);
    try {
      for (const file of [sales, stock]) {
        const problem = file ? await checkUpload(file) : null;
        if (file && problem) {
          setProblems([`${file.name}: ${{ type: t.uploadBadType, size: t.uploadTooBig, binary: t.uploadBinary }[problem]}`]);
          return;
        }
      }
      onData(await upload(sales, stock));
    } catch (error) {
      const list = error instanceof UploadError ? error.problems : ["?"];
      setProblems(list.map((p) => (p === "API_UNREACHABLE" ? t.apiDown : p)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="upload-h" className="card">
      <h2 id="upload-h">{t.uploadTitle}</h2>
      <p className="hint">{t.uploadIntro}</p>
      <form onSubmit={submit} className="upload-form">
        <label>
          {t.salesFile}
          <input
            type="file"
            accept=".csv,text/csv"
            aria-required="true"
            onChange={(e) => setSales(e.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          {t.stockFile}
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setStock(e.target.files?.[0] ?? null)}
          />
        </label>
        <div className="row">
          <button type="submit" className="btn primary" disabled={busy || !sales}>
            {t.analyze}
          </button>
          {showReset && (
            <button type="button" className="btn" onClick={onReset}>
              {t.backToDemo}
            </button>
          )}
        </div>
      </form>
      <p role="status">{busy ? t.analyzing : ""}</p>
      {problems.length > 0 && (
        <div role="alert" className="problems">
          <strong>{t.problemsTitle}</strong>
          <ul>
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
