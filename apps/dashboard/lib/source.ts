import type { DashboardData } from "./types";

/**
 * Where the dashboard gets its data.
 *
 * Default: the bundled synthetic demo file. If NEXT_PUBLIC_API_URL is set the
 * dashboard calls the real API instead (the endpoint is planned, see
 * docs/architecture/dashboard.md); the demo file stays the fallback.
 */
export async function loadData(
  fetchImpl: typeof fetch = fetch,
  apiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL,
): Promise<DashboardData> {
  const url = apiUrl ? `${apiUrl.replace(/\/$/, "")}/v1/dashboard` : "/demo/data.json";
  const response = await fetchImpl(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Data request failed with status ${response.status}`);
  }
  return validate(await response.json());
}

/** Minimal runtime check: never render a payload with the wrong shape. */
export function validate(payload: unknown): DashboardData {
  const data = payload as Partial<DashboardData> | null;
  if (!data || !Array.isArray(data.items) || typeof data.as_of !== "string") {
    throw new Error("Unexpected data format");
  }
  return data as DashboardData;
}
