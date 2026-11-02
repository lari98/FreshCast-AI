/* FreshCast service worker: lets the dashboard open and work without a network.
 *
 * Generated into public/sw.js by scripts/write-version.mjs, which fills in BUILD, so every
 * build installs a new worker with its own cache and removes the old one. Rules:
 *  - only same-origin GET requests are handled; the API, uploads and everything else go
 *    straight to the network (nothing a user uploads is ever stored here);
 *  - /version.json (update detection) and this file are never cached;
 *  - hashed build files (/_next/static/) are cache-first, they can never change;
 *  - pages are network-first and fall back to the saved copy (also while a rebuild makes
 *    the server briefly answer 404);
 *  - demo data is stale-while-revalidate.
 * The shell is stored at install time; if that fails (for example offline) the old worker
 * simply stays in charge.
 */
const BUILD = "__BUILD__";
const CACHE = "freshcast-" + BUILD;
const PREFIX = "freshcast-";
const EXTRA = ["/demo/data.json", "/demo/replay.json"];
const ASSET = /\/_next\/static\/[A-Za-z0-9_\-./%~]+\.(?:js|css|woff2)/g;
const OFFLINE_PAGE =
  "<!doctype html><meta charset=utf-8><title>FreshCast offline</title><p style=\"font:16px system-ui;padding:2rem\">" +
  "Offline, and this page has not been saved yet. Open FreshCast once while online.</p>";

const key = (request) => new URL(typeof request === "string" ? request : request.url, self.location.origin).pathname;
const keep = (response) => response && response.ok && response.type !== "opaque" && response.type !== "error";

async function put(cache, request, response) {
  if (keep(response)) await cache.put(key(request), response.clone());
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (keep(response)) {
      await put(cache, request, response);
      return response;
    }
    return (await cache.match(key(request))) || (await cache.match("/")) || response;
  } catch {
    return (
      (await cache.match(key(request))) ||
      (await cache.match("/")) ||
      new Response(OFFLINE_PAGE, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } })
    );
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(key(request));
  if (hit) return hit;
  const response = await fetch(request);
  await put(cache, request, response);
  return response;
}

async function staleWhileRevalidate(event) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(key(event.request));
  const fresh = fetch(event.request)
    .then(async (response) => {
      await put(cache, event.request, response);
      return response;
    })
    .catch(() => undefined);
  if (hit) {
    event.waitUntil(fresh);
    return hit;
  }
  return (await fresh) || new Response("offline", { status: 503 });
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      const shell = await fetch("/", { cache: "reload" });
      if (!shell.ok) throw new Error("shell not available");
      const html = await shell.clone().text();
      const assets = [...new Set(html.match(ASSET) ?? [])];
      await cache.put("/", shell);
      await Promise.all(
        assets.map(async (url) => {
          const response = await fetch(url, { cache: "reload" });
          if (!response.ok) throw new Error("asset not available: " + url);
          await cache.put(url, response);
        }),
      );
      await Promise.all(
        EXTRA.map(async (url) => {
          try {
            await put(cache, url, await fetch(url, { cache: "reload" }));
          } catch {
            /* optional data; fetched on demand later */
          }
        }),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const name of await caches.keys()) {
        if (name.startsWith(PREFIX) && name !== CACHE) await caches.delete(name);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const path = url.pathname;
  if (path === "/version.json" || path === "/sw.js" || path === "/healthz") return;
  if (path.startsWith("/_next/static/")) event.respondWith(cacheFirst(request));
  else if (path.startsWith("/demo/")) event.respondWith(staleWhileRevalidate(event));
  else if (request.mode === "navigate") event.respondWith(networkFirst(request));
});
