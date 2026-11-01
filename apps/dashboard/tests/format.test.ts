import { describe, expect, it } from "vitest";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { validate } from "@/lib/source";

describe("format", () => {
  it("uses locale separators", () => {
    expect(formatNumber(1234.5, "de", 1)).toBe("1.234,5");
    expect(formatNumber(1234.5, "en", 1)).toBe("1,234.5");
  });
  it("formats dates without timezone drift", () => {
    expect(formatDate("2025-12-22", "de")).toBe("22.12.2025");
    expect(formatDate("2025-12-22", "en")).toBe("22/12/2025");
  });
  it("formats CHF and EUR", () => {
    expect(formatCurrency(5, "EUR", "de")).toContain("€");
    expect(formatCurrency(5, "CHF", "de")).toContain("CHF");
  });
});

describe("validate", () => {
  it("rejects malformed payloads", () => {
    expect(() => validate(null)).toThrow();
    expect(() => validate({ items: "x" })).toThrow();
  });
  it("accepts a minimal payload", () => {
    expect(validate({ items: [], as_of: "2025-12-22" }).items).toEqual([]);
  });
});
