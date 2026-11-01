import type { SeriesPoint } from "./types";

export interface Accuracy {
  days: number;
  /** Weighted absolute percentage error: sum|a-p| / sum a. */
  wape: number | null;
  /** (sum p - sum a) / sum a. Positive = over-forecast. */
  bias: number | null;
  /** Share of days where the actual fell inside [lower, upper]. */
  coverage: number | null;
}

/** Accuracy over trading days that already have an actual value. */
export function accuracy(series: SeriesPoint[]): Accuracy {
  const rows = series.filter((p) => p.actual !== null && p.is_open);
  const actual = rows.reduce((s, p) => s + (p.actual ?? 0), 0);
  if (rows.length === 0 || actual === 0) {
    return { days: rows.length, wape: null, bias: null, coverage: null };
  }
  const abs = rows.reduce((s, p) => s + Math.abs((p.actual ?? 0) - p.point), 0);
  const signed = rows.reduce((s, p) => s + (p.point - (p.actual ?? 0)), 0);
  const inside = rows.filter(
    (p) => (p.actual ?? 0) >= p.lower && (p.actual ?? 0) <= p.upper,
  ).length;
  return {
    days: rows.length,
    wape: abs / actual,
    bias: signed / actual,
    coverage: inside / rows.length,
  };
}

/** Pool several series (sums are pooled, not averaged, so big items weigh more). */
export function pooledAccuracy(all: SeriesPoint[][]): Accuracy {
  return accuracy(all.flat());
}
