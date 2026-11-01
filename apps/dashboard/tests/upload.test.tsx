import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { Dashboard } from "@/components/Dashboard";
import { UploadError, analyzeUpload } from "@/lib/source";
import type { DashboardData } from "@/lib/types";

const demo = JSON.parse(
  readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8"),
) as DashboardData;

const uploaded: DashboardData = {
  ...demo,
  source: "upload",
  quality: {
    rows_in: 10, rows_used: 12, series_used: 1, skipped: ["X/Y: only 3 days of history"],
    warnings: ["no stock file: shelves are assumed empty"],
    date_from: "2025-05-06", date_to: "2025-12-31", calibrated: true,
  },
  items: demo.items.slice(0, 1),
};

const csv = (name: string) => new File(["a;b\n1;2\n"], name, { type: "text/csv" });

async function renderWith(upload: typeof analyzeUpload) {
  const { UploadPanel } = await import("@/components/UploadPanel");
  const { STRINGS } = await import("@/lib/i18n");
  const onData = vi.fn();
  render(<UploadPanel t={STRINGS.de} onData={onData} onReset={() => {}} showReset={false} upload={upload} />);
  return onData;
}

describe("UploadPanel", () => {
  it("disables Analysieren until a sales file is chosen, then passes the result on", async () => {
    const upload = vi.fn(async () => uploaded);
    const onData = await renderWith(upload);
    const button = screen.getByRole("button", { name: "Analysieren" });
    expect(button).toBeDisabled();
    await userEvent.upload(screen.getByLabelText(/Absatzdatei/), csv("absatz.csv"));
    await userEvent.click(button);
    await waitFor(() => expect(onData).toHaveBeenCalledWith(uploaded));
  });

  it("lists the problems the API returns", async () => {
    const upload = vi.fn(async () => {
      throw new UploadError(["missing required column(s): business_date"]);
    });
    await renderWith(upload);
    await userEvent.upload(screen.getByLabelText(/Absatzdatei/), csv("x.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Analysieren" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("business_date");
  });

  it("explains how to start the API when it is unreachable", async () => {
    const upload = vi.fn(async () => {
      throw new UploadError(["API_UNREACHABLE"]);
    });
    await renderWith(upload);
    await userEvent.upload(screen.getByLabelText(/Absatzdatei/), csv("x.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Analysieren" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nicht erreichbar");
  });
});

describe("analyzeUpload", () => {
  it("posts multipart data with dev headers and parses the payload", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(uploaded), { status: 200 }));
    const out = await analyzeUpload(csv("s.csv"), csv("b.csv"), fetchMock as unknown as typeof fetch, "http://api.test/");
    expect(out.source).toBe("upload");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.test/v1/analyze");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).has("stock")).toBe(true);
  });

  it("turns a 422 into an UploadError with the problem list", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ detail: { problems: ["bad date"] } }), { status: 422 }),
    );
    await expect(
      analyzeUpload(csv("s.csv"), null, fetchMock as unknown as typeof fetch, "http://api.test"),
    ).rejects.toMatchObject({ problems: ["bad date"] });
  });

  it("reports an unreachable API", async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError("network");
    });
    await expect(
      analyzeUpload(csv("s.csv"), null, fetchMock as unknown as typeof fetch, "http://api.test"),
    ).rejects.toMatchObject({ problems: ["API_UNREACHABLE"] });
  });
});

describe("Dashboard with an upload result", () => {
  it("shows the data-quality panel and the upload banner, and stays accessible", async () => {
    window.history.replaceState(null, "", "#data");
    const { container } = render(<Dashboard load={async () => uploaded} />);
    expect(await screen.findByRole("heading", { name: "Datenqualität" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("hochgeladenen");
    expect(screen.getByText(/shelves are assumed empty/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
