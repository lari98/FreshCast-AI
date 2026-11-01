// Writes public/version.json so open tabs can notice a new deployment.
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

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
