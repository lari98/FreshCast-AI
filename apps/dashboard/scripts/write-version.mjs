// Writes public/version.json so open tabs can notice a new deployment.
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

let build = process.env.NEXT_PUBLIC_BUILD || "";
if (!build) {
  try {
    build = execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    /* not a git checkout (for example the Windows copy) */
  }
}
mkdirSync("public", { recursive: true });
writeFileSync("public/version.json", JSON.stringify({ build: build || "local", at: new Date().toISOString() }) + "\n");

// The service worker is generated per build: a new id makes browsers install it as an update,
// and the worker then replaces the previous build's cache.
const swId = `${build || "local"}-${Date.now().toString(36)}`;
const template = readFileSync(new URL("./sw.template.js", import.meta.url), "utf-8");
writeFileSync("public/sw.js", template.replace("__BUILD__", swId));
