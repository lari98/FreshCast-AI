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

/** The API rejected the upload; ``problems`` says what to fix. */
export class UploadError extends Error {
  constructor(public readonly problems: string[]) {
    super(problems.join("; "));
  }
}

const DEV_HEADERS = { "x-dev-user": "dashboard", "x-dev-role": "store_manager" };

/**
 * Send the user's CSV files to the local API and return the forecast payload.
 * The dev headers only work when the API runs with FRESHCAST_ENV=local; a
 * deployed API requires real sign-in instead (planned).
 */
export async function analyzeUpload(
  sales: File,
  stock: File | null,
  fetchImpl: typeof fetch = fetch,
  apiUrl: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
): Promise<DashboardData> {
  const form = new FormData();
  form.append("sales", sales);
  if (stock) form.append("stock", stock);
  let response: Response;
  try {
    response = await fetchImpl(`${apiUrl.replace(/\/$/, "")}/v1/analyze`, {
      method: "POST",
      headers: DEV_HEADERS,
      body: form,
    });
  } catch {
    throw new UploadError(["API_UNREACHABLE"]);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: { problems?: string[] } | string;
    } | null;
    const detail = body?.detail;
    throw new UploadError(
      typeof detail === "object" && detail?.problems
        ? detail.problems
        : [`HTTP ${response.status}`],
    );
  }
  return validate(await response.json());
}
