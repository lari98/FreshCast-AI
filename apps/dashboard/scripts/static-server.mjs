// Tiny static file server for the exported dashboard (no dependencies).
// Usage: node scripts/static-server.mjs [dir=out] [port=3000]
import { createReadStream, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { createGzip } from "node:zlib";

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2", ".csv": "text/csv; charset=utf-8",
};
const COMPRESSIBLE = new Set([".html", ".js", ".css", ".json", ".txt", ".svg", ".csv"]);

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

export function makeServer(root) {
  return createServer((req, res) => {
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405, { Allow: "GET, HEAD" }).end();
      return;
    }
    const file = find(root, req.url ?? "/");
    const headers = {
      "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    };
    if (!file) {
      // During a rebuild the files vanish for a moment: ask the browser to retry.
      res.writeHead(404, { ...headers, "Content-Type": "text/plain" }).end("Not found");
      return;
    }
    const ext = extname(file).toLowerCase();
    headers["Content-Type"] = TYPES[ext] ?? "application/octet-stream";
    headers["Cache-Control"] = file.includes(`${sep}_next${sep}static${sep}`)
      ? "public, max-age=31536000, immutable"
      : "no-cache";
    const gzip = COMPRESSIBLE.has(ext) && /\bgzip\b/.test(req.headers["accept-encoding"] ?? "");
    if (gzip) headers["Content-Encoding"] = "gzip";
    res.writeHead(200, headers);
    if (req.method === "HEAD") return void res.end();
    const stream = createReadStream(file);
    stream.on("error", () => res.destroy());
    (gzip ? stream.pipe(createGzip()) : stream).pipe(res);
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  const root = process.argv[2] ?? "out";
  const port = Number(process.argv[3] ?? 3000);
  makeServer(root).listen(port, "127.0.0.1", () => console.log(`Serving ${resolve(root)} on http://localhost:${port}`));
}
