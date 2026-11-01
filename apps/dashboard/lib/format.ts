import type { Lang } from "./types";

const LOCALE: Record<Lang, string> = { de: "de-DE", en: "en-GB" };

/** Locale-aware number, e.g. 1.234,5 (de) vs 1,234.5 (en). */
export function formatNumber(value: number, lang: Lang, digits = 0): string {
  return new Intl.NumberFormat(LOCALE[lang], {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

/** Calendar date from an ISO yyyy-mm-dd string. Parsed as UTC to avoid DST shifts. */
export function formatDate(iso: string, lang: Lang): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE[lang], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)));
}

export function formatCurrency(
  value: number,
  currency: "EUR" | "CHF",
  lang: Lang,
): string {
  return new Intl.NumberFormat(LOCALE[lang], {
    style: "currency",
    currency,
  }).format(value);
}
