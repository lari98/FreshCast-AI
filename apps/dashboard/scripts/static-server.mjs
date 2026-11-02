// Small static file server for the exported dashboard (no dependencies).
// Usage: node scripts/static-server.mjs [dir=out] [port=3000]
//
// Built to be cheap to run: each file is compressed once (Brotli and gzip) and kept in
// memory, answers carry an ETag so a reload costs a tiny 304 instead of a download,
// and an idle server uses no CPU (no timers, no file watching).
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { brotliCompressSync, constants, gzipSync } from "node:zlib";

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2", ".csv": "text/csv; charset=utf-8",
};
const COMPRESSIBLE = new Set([".html", ".js", ".css", ".json", ".txt", ".svg", ".csv"]);
const MAX_URL = 2048;
const MAX_CACHE_BYTES = 64 * 2 ** 20; // memory cap for cached copies
const MIN_COMPRESS = 512; // below this, compression saves nothing

// Same-origin policy as the meta tag in app/layout.tsx, plus the directives a meta tag cannot carry.
const CSP = [
  "default-src 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:", "font-src 'self'", "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",
  "object-src 'none'", "base-uri 'none'", "form-action 'self'", "frame-ancestors 'none'",
].join("; ");
const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
  "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
  "Content-Security-Policy": CSP,
};

/** Map a URL path to a file inside root, or null when it would leave root (path traversal). */
export function safeResolve(root, urlPath) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath.split("?")[0].split("#")[0]);
  } catch {
    return null;
  }
  if (decoded.includes("\0")) return null;
  const base = resolve(root);
  const target = resolve(join(base, normalize(decoded)));
  return target === base || target.startsWith(base + sep) ? target : null;
}

function find(root, urlPath) {
  const target = safeResolve(root, urlPath);
  if (!target) return null;
  for (const candidate of [target, join(target, "index.html"), `${target}.html`]) {
    try {
      if (statSync(candidate).isFile()) return candidate;
    } catch {
      /* try the next candidate */
    }
  }
  return null;
}

/** Read and compress a file once; recomputed only when its size or modification time changes. */
function makeCache() {
  const entries = new Map();
  let bytes = 0;
  return (file, ext) => {
    const st = statSync(file);
    const stamp = `${st.size}-${Math.floor(st.mtimeMs)}`;
    const hit = entries.get(file);
    if (hit && hit.stamp === stamp) return hit;
    const raw = readFileSync(file);
    const etag = `"${createHash("sha1").update(raw).digest("base64url").slice(0, 22)}"`;
    const entry = { stamp, raw, etag, br: null, gzip: null, size: 0 };
    if (COMPRESSIBLE.has(ext) && raw.length >= MIN_COMPRESS) {
      const br = brotliCompressSync(raw, {
        params: { [constants.BROTLI_PARAM_QUALITY]: 9, [constants.BROTLI_PARAM_SIZE_HINT]: raw.length },
      });
      const gz = gzipSync(raw, { level: 9 });
      if (br.length < raw.length) entry.br = br;
      if (gz.length < raw.length) entry.gzip = gz;
    }
    entry.size = raw.length + (entry.br?.length ?? 0) + (entry.gzip?.length ?? 0);
    if (hit) bytes -= hit.size;
    if (bytes + entry.size <= MAX_CACHE_BYTES) {
      entries.set(file, entry);
      bytes += entry.size;
    } else {
      entries.delete(file); // over the cap: serve this one uncached
    }
    return entry;
  };
}

export function makeServer(root) {
  const load = makeCache();
  const server = createServer((req, res) => {
    const headers = { ...SECURITY_HEADERS };
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405, { ...headers, Allow: "GET, HEAD" }).end();
      return;
    }
    const url = req.url ?? "/";
    if (url.length > MAX_URL) {
      res.writeHead(414, { ...headers, "Content-Type": "text/plain" }).end("URI too long");
      return;
    }
    if (url === "/healthz") {
      res.writeHead(200, { ...headers, "Content-Type": "text/plain", "Cache-Control": "no-store" }).end("ok");
      return;
    }
    const file = find(root, url);
    if (!file) {
      // During a rebuild the files vanish for a moment; the update watcher simply asks again later.
      res.writeHead(404, { ...headers, "Content-Type": "text/plain" }).end("Not found");
      return;
    }
    const ext = extname(file).toLowerCase();
    let entry;
    try {
      entry = load(file, ext);
    } catch {
      res.writeHead(503, { ...headers, "Content-Type": "text/plain", "Retry-After": "2" }).end("Try again");
      return;
    }
    headers["Content-Type"] = TYPES[ext] ?? "application/octet-stream";
    headers["Cache-Control"] = file.includes(`${sep}_next${sep}static${sep}`)
      ? "public, max-age=31536000, immutable"
      : "no-cache"; // revalidate every time, but with an ETag the answer is a 304 without a body
    headers.ETag = entry.etag;
    headers.Vary = "Accept-Encoding";
    if (req.headers["if-none-match"] === entry.etag) {
      res.writeHead(304, headers).end();
      return;
    }
    const accept = req.headers["accept-encoding"] ?? "";
    let body = entry.raw;
    if (entry.br && /\bbr\b/.test(accept)) {
      body = entry.br;
      headers["Content-Encoding"] = "br";
    } else if (entry.gzip && /\bgzip\b/.test(accept)) {
      body = entry.gzip;
      headers["Content-Encoding"] = "gzip";
    }
    headers["Content-Length"] = body.length;
    res.writeHead(200, headers);
    res.end(req.method === "HEAD" ? undefined : body);
  });
  // A stalled or slow client must not hold a connection (and memory) open indefinitely.
  server.headersTimeout = 10_000;
  server.requestTimeout = 15_000;
  server.keepAliveTimeout = 5_000;
  server.maxHeadersCount = 50;
  server.on("clientError", (_err, socket) => {
    if (socket.writable) socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
  });
  return server;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  const root = process.argv[2] ?? "out";
  const port = Number(process.argv[3] ?? 3000);
  const server = makeServer(root);
  server.listen(port, "127.0.0.1", () => console.log(`Serving ${resolve(root)} on http://localhost:${port}`));
  const stop = () => server.close(() => process.exit(0));
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}
