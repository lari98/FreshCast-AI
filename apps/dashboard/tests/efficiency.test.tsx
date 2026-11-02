import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "@/components/Dashboard";
import { TabBoundary } from "@/components/TabBoundary";
import { UpdateWatcher } from "@/components/UpdateWatcher";
import { STRINGS } from "@/lib/i18n";
import type { Replay } from "@/lib/replay";
import type { DashboardData } from "@/lib/types";

const data = JSON.parse(readFileSync(join(__dirname, "../public/demo/data.json"), "utf-8")) as DashboardData;
const replay = JSON.parse(readFileSync(join(__dirname, "../public/demo/replay.json"), "utf-8")) as Replay;

const setVisibility = (state: "visible" | "hidden") => {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
  document.dispatchEvent(new Event("visibilitychange"));
};
const ok = (build = "aaa") => vi.fn(async () => new Response(JSON.stringify({ build })));

beforeEach(() => {
  window.history.replaceState(null, "", "#");
  window.localStorage.clear();
});
afterEach(() => {
  vi.useRealTimers();
  setVisibility("visible");
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => true });
});

describe("update watcher: cheap by design", () => {
  it("does not poll while the tab is hidden and resumes when it is shown again", async () => {
    vi.useFakeTimers();
    const f = ok();
    render(<UpdateWatcher t={STRINGS.de} busy={false} intervalMs={1000} fetchImpl={f as unknown as typeof fetch} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(f).toHaveBeenCalledTimes(1);
    act(() => setVisibility("hidden"));
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(f).toHaveBeenCalledTimes(1); // a minute hidden: zero requests
    act(() => setVisibility("visible"));
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(f).toHaveBeenCalledTimes(2); // looks once on return
  });

  it("makes no request while offline", async () => {
    vi.useFakeTimers();
    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => false });
    const f = ok();
    render(<UpdateWatcher t={STRINGS.de} busy={false} intervalMs={1000} fetchImpl={f as unknown as typeof fetch} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(f).not.toHaveBeenCalled();
  });

  it("backs off after errors instead of hammering a down server", async () => {
    vi.useFakeTimers();
    const f = vi.fn(async () => { throw new Error("down"); });
    render(<UpdateWatcher t={STRINGS.de} busy={false} intervalMs={1000} fetchImpl={f as unknown as typeof fetch} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(31_000); });
    // delays 1 s, 2 s, 4 s, 8 s, 16 s: six calls in 31 s instead of 31
    expect(f.mock.calls.length).toBeLessThanOrEqual(6);
    expect(f.mock.calls.length).toBeGreaterThanOrEqual(4);
  });

  it("asks the browser to revalidate (304) instead of downloading again", async () => {
    const f = ok();
    render(<UpdateWatcher t={STRINGS.de} busy={false} fetchImpl={f as unknown as typeof fetch} />);
    await act(async () => { await Promise.resolve(); });
    expect(f).toHaveBeenCalledWith("/version.json", { cache: "no-cache" });
  });
});

describe("energy-saving mode", () => {
  const open = async () => {
    render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
  };

  it("is off by default, can be switched on in the settings and is remembered", async () => {
    await open();
    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));
    const box = screen.getByRole("checkbox", { name: "Energiesparmodus" });
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    expect(box).toBeChecked();
    expect(JSON.parse(window.localStorage.getItem("freshcast.settings.v2") ?? "{}").eco).toBe(true);
  });

  it("starts in energy-saving mode when the browser asks for less data", async () => {
    Object.defineProperty(navigator, "connection", { configurable: true, value: { saveData: true } });
    await open();
    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));
    expect(screen.getByRole("checkbox", { name: "Energiesparmodus" })).toBeChecked();
    Reflect.deleteProperty(navigator, "connection");
  });

  it("shows 25 instead of 100 rows per page", async () => {
    window.localStorage.setItem("freshcast.settings.v2", JSON.stringify({ eco: true }));
    const big = { ...data, items: Array.from({ length: 5 }, (_, c) => data.items.map((it) => ({ ...it, store_id: it.store_id.replace(/-\d+$/, `-0${c + 1}`) }))).flat() };
    render(<Dashboard load={async () => big} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
    await userEvent.click(screen.getByRole("tab", { name: "Bestellungen" }));
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(1 + 25 + 1);
  });
});

describe("damaged browser storage", () => {
  it.each(["{not json", "[]", "null", JSON.stringify({ eco: "yes", costShare: 99, theme: "neon", role: "root", markets: [1, 2], workflow: "x" })])(
    "starts normally with %s in the saved settings", async (saved) => {
      window.localStorage.setItem("freshcast.settings.v2", saved);
      render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
      expect(await screen.findByRole("tablist")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));
      expect(screen.getByRole("checkbox", { name: "Energiesparmodus" })).not.toBeChecked();
    },
  );
});

describe("one broken tab does not break the dashboard", () => {
  const Boom = () => { throw new Error("secret detail from an upload"); };

  it("shows a calm message without the error text, and recovers when the tab changes", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { rerender } = render(<TabBoundary t={STRINGS.de} resetKey="a"><Boom /></TabBoundary>);
    expect(screen.getByRole("alert")).toHaveTextContent("konnte nicht angezeigt werden");
    expect(screen.queryByText(/secret detail/)).toBeNull();
    rerender(<TabBoundary t={STRINGS.de} resetKey="b"><p>fine</p></TabBoundary>);
    expect(screen.getByText("fine")).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe("offline use", () => {
  afterEach(() => { Reflect.deleteProperty(navigator, "serviceWorker"); vi.unstubAllEnvs(); });

  it("tells the user when the browser has no network and when it is back", async () => {
    render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(screen.getByText(/Sie sind offline/)).toBeInTheDocument();
    act(() => { window.dispatchEvent(new Event("online")); });
    expect(screen.queryByText(/Sie sind offline/)).toBeNull();
  });

  it("registers the worker in a finished build, shows it is ready and can remove the offline copy", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const unregister = vi.fn(async () => true);
    const deleted: string[] = [];
    const register = vi.fn(async () => ({}));
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register, ready: Promise.resolve({}), getRegistrations: async () => [{ unregister }] },
    });
    vi.stubGlobal("caches", { keys: async () => ["freshcast-1", "other"], delete: async (n: string) => { deleted.push(n); return true; } });
    render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));
    expect(await screen.findByText("Offline bereit")).toBeInTheDocument();
    expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/", updateViaCache: "none" });
    await userEvent.click(screen.getByRole("button", { name: "Offline-Kopie löschen" }));
    expect(await screen.findByText("Offline-Kopie entfernt")).toBeInTheDocument();
    expect(unregister).toHaveBeenCalled();
    expect(deleted).toEqual(["freshcast-1"]); // only its own cache
    vi.unstubAllGlobals();
  });

  it("explains when offline use is unavailable (development build)", async () => {
    render(<Dashboard load={async () => data} loadReplay={async () => replay} />);
    await screen.findByRole("tablist");
    await userEvent.click(screen.getByRole("tab", { name: "Einstellungen" }));
    expect(await screen.findByText(/Offline-Nutzung ist hier nicht verfügbar/)).toBeInTheDocument();
  });
});
