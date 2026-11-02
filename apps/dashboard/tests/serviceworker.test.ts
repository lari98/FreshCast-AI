import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";

const SOURCE = readFileSync(join(__dirname, "../scripts/sw.template.js"), "utf-8");
const ORIGIN = "https://fc.test";

type Handler = (event: Record<string, unknown>) => void;

/** Runs the real worker source against a small fake of the worker environment. */
function boot(build: string, network: (url: string) => Response | Promise<Response>, store = new Map<string, Map<string, Response>>()) {
  const handlers: Record<string, Handler> = {};
  const fetchSpy = vi.fn(async (input: string | { url: string }) => {
    const url = typeof input === "string" ? input : input.url;
    return network(new URL(url, ORIGIN).pathname);
  });
  const k = (r: string | { url: string }) => new URL(typeof r === "string" ? r : r.url, ORIGIN).pathname;
  const open = async (name: string) => {
    if (!store.has(name)) store.set(name, new Map());
    const m = store.get(name)!;
    return {
      put: async (r: string | { url: string }, res: Response) => void m.set(k(r), res),
      match: async (r: string | { url: string }) => m.get(k(r))?.clone(),
    };
  };
  const sandbox = {
    self: {
      location: { origin: ORIGIN },
      addEventListener: (type: string, fn: Handler) => { handlers[type] = fn; },
      skipWaiting: vi.fn(async () => undefined),
      clients: { claim: vi.fn(async () => undefined) },
    },
    caches: { open, keys: async () => [...store.keys()], delete: async (n: string) => store.delete(n) },
    fetch: fetchSpy, Response, URL, Set, Promise, Array,
  };
  vm.runInNewContext(SOURCE.replace("__BUILD__", build), sandbox);
  const run = async (type: string, extra: Record<string, unknown> = {}) => {
    const waits: Promise<unknown>[] = [];
    let answer: Promise<Response> | undefined;
    handlers[type]!({ waitUntil: (p: Promise<unknown>) => waits.push(p), respondWith: (p: Promise<Response>) => { answer = p; }, ...extra });
    await Promise.all(waits);
    return answer;
  };
  const get = (path: string, mode = "cors", method = "GET", origin = ORIGIN) =>
    run("fetch", { request: { url: origin + path, method, mode } });
  return { run, get, fetchSpy, store, sandbox };
}

const html = '<script src="/_next/static/chunks/a.js"></script><link href="/_next/static/chunks/b.css"><p>x \\"/_next/static/chunks/c.js\\"</p>';
const site = (path: string): Response => {
  if (path === "/") return new Response(html);
  if (path.startsWith("/_next/static/")) return new Response("asset " + path);
  if (path.startsWith("/demo/")) return new Response('{"n":1}');
  return new Response("nope", { status: 404 });
};

describe("service worker", () => {
  it("stores the shell, every build file named in it and the demo data at install", async () => {
    const w = boot("b1", site);
    await w.run("install");
    const cache = w.store.get("freshcast-b1")!;
    expect([...cache.keys()].sort()).toEqual([
      "/", "/_next/static/chunks/a.js", "/_next/static/chunks/b.css", "/_next/static/chunks/c.js", "/demo/data.json", "/demo/replay.json",
    ]);
    expect(w.sandbox.self.skipWaiting).toHaveBeenCalled();
  });

  it("fails the install (the old worker stays) when the shell or a build file is missing", async () => {
    await expect(boot("b", () => new Response("", { status: 500 })).run("install")).rejects.toThrow();
    await expect(boot("b", (p) => (p.endsWith("a.js") ? new Response("", { status: 404 }) : site(p))).run("install")).rejects.toThrow();
    const w = boot("b", () => { throw new Error("offline"); });
    await expect(w.run("install")).rejects.toThrow();
    expect(w.sandbox.self.skipWaiting).not.toHaveBeenCalled();
  });

  it("never touches version.json, itself, other origins, the API or non-GET requests", async () => {
    const w = boot("b1", site);
    expect(await w.get("/version.json", "navigate")).toBeUndefined();
    expect(await w.get("/sw.js", "navigate")).toBeUndefined();
    expect(await w.get("/v1/analyze", "cors", "POST")).toBeUndefined();
    expect(await w.get("/_next/static/x.js", "cors", "GET", "https://evil.test")).toBeUndefined();
    expect(await w.get("/v1/items", "cors")).toBeUndefined(); // same origin, but not a page or asset
    expect(w.fetchSpy).not.toHaveBeenCalled();
  });

  it("serves hashed build files from the cache after the first request", async () => {
    const w = boot("b1", site);
    await (await w.get("/_next/static/chunks/z.js"))!.text();
    const again = await w.get("/_next/static/chunks/z.js");
    expect(await again!.text()).toBe("asset /_next/static/chunks/z.js");
    expect(w.fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("opens pages from the network and falls back to the saved copy offline or on 404", async () => {
    let up = true;
    let code = 200;
    const w = boot("b1", (p) => {
      if (!up) throw new Error("offline");
      return code === 200 ? site(p) : new Response("rebuilding", { status: code });
    });
    expect(await (await w.get("/", "navigate"))!.text()).toBe(html);
    up = false;
    expect(await (await w.get("/", "navigate"))!.text()).toBe(html);
    expect(await (await w.get("/some/other/page", "navigate"))!.text()).toBe(html); // falls back to the shell
    up = true;
    code = 404;
    expect(await (await w.get("/", "navigate"))!.text()).toBe(html); // server mid-rebuild
  });

  it("shows a plain offline page when nothing has been saved yet, and never saves errors", async () => {
    const w = boot("b1", () => { throw new Error("offline"); });
    const res = (await w.get("/", "navigate"))!;
    expect(res.status).toBe(503);
    expect(await res.text()).toContain("Open FreshCast once while online");
    const e = boot("b1", () => new Response("boom", { status: 500 }));
    await e.get("/_next/static/chunks/q.js");
    expect([...(e.store.get("freshcast-b1")?.keys() ?? [])]).toEqual([]);
  });

  it("answers demo data from the cache and refreshes it in the background", async () => {
    let value = "old";
    const w = boot("b1", () => new Response(value));
    expect(await (await w.get("/demo/data.json"))!.text()).toBe("old");
    value = "new";
    expect(await (await w.get("/demo/data.json"))!.text()).toBe("old"); // instant, stale
    expect(await (await w.get("/demo/data.json"))!.text()).toBe("new"); // refreshed by the previous visit
  });

  it("removes the caches of older builds, but only its own kind, when it takes over", async () => {
    const store = new Map<string, Map<string, Response>>([
      ["freshcast-old1", new Map()], ["freshcast-b2", new Map()], ["someone-elses", new Map()],
    ]);
    const w = boot("b2", site, store);
    await w.run("activate");
    expect([...store.keys()].sort()).toEqual(["freshcast-b2", "someone-elses"]);
    expect(w.sandbox.self.clients.claim).toHaveBeenCalled();
  });
});
