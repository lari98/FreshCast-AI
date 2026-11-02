import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, test } from "node:test";
import { makeServer, safeResolve } from "./static-server.mjs";

const root = mkdtempSync(join(tmpdir(), "fc-static-"));
mkdirSync(join(root, "_next", "static"), { recursive: true });
writeFileSync(join(root, "index.html"), "<h1>ok</h1>");
writeFileSync(join(root, "_next", "static", "a.js"), "x".repeat(2000));
writeFileSync(join(tmpdir(), "fc-secret.txt"), "secret");
const server = makeServer(root);
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
after(() => server.close());
const base = () => `http://127.0.0.1:${server.address().port}`;

test("path traversal is refused", async () => {
  for (const p of ["/../fc-secret.txt", "/%2e%2e/fc-secret.txt", "/..%2f..%2fetc/passwd", "/\0", "/%00", "/%zz"]) {
    const got = safeResolve(root, p);
    assert.ok(got === null || got.startsWith(root), `${p} escaped the root: ${got}`);
  }
  const etc = safeResolve(root, "/../../etc/passwd");
  assert.ok(etc === null || etc.startsWith(root)); // never the real /etc/passwd
  const r = await fetch(`${base()}/..%2f..%2f..%2fetc%2fpasswd`);
  assert.notEqual(r.status, 200);
});

test("serves the index, compresses, caches static assets and sets headers", async () => {
  const home = await fetch(`${base()}/`);
  assert.equal(home.status, 200);
  assert.equal(home.headers.get("x-content-type-options"), "nosniff");
  assert.equal(home.headers.get("cache-control"), "no-cache");
  const js = await fetch(`${base()}/_next/static/a.js`, { headers: { "accept-encoding": "gzip" } });
  assert.equal(js.headers.get("content-encoding"), "gzip");
  assert.match(js.headers.get("cache-control"), /immutable/);
});

test("only GET and HEAD are allowed", async () => {
  assert.equal((await fetch(`${base()}/`, { method: "POST" })).status, 405);
});
