# How FreshCast is protected, and how safe you are

Plain answer first: **no system is unhackable, and this one does not claim to be.**
What it does is use several independent layers, so that one failure does not become a
break-in, and test those layers with real attacks (see [attack-testing.md](attack-testing.md)).

## What happens to a hostile file
```
file chosen  ->  browser check  ->  API checks  ->  optional ClamAV  ->  parsed as text  ->  cleaned cells
   (1)              (2)               (3)              (4)                  (5)                (6)
```
1. **Browser check** (`uploadGuard.ts`): wrong extension, path in the name, executable file type,
   size over 25 MB, or the first bytes of a program, archive, PDF, Office file or image.
   Nothing leaves your computer if it fails. This is for fast feedback only; it can be bypassed,
   so the server repeats everything.
2. **API checks** (`upload_guard.py`): the same signatures, NUL bytes, control characters, very long
   lines, more than 100 columns, `<script>`, `<iframe>`, `<?php`, `javascript:` and similar payloads.
   The file name is checked too. A refusal returns HTTP 422 with a reason.
3. **Malware scanner (optional)**: set `FRESHCAST_CLAMD_HOST` to a ClamAV daemon and every upload is
   scanned with its signatures. If the scanner is configured but unreachable, the upload is
   **refused** (fail closed). ClamAV is not bundled; without it only the structural checks run.
4. **Never executed, never stored**: the file is read into memory as text. It is not written to
   disk, not opened by Office, not run. A payload that slips past every check has nothing that
   would run it.
5. **Cell cleaning**: control characters removed, leading `= + - @` stripped from text columns
   (spreadsheet formula injection), names cut to 80 characters, store and SKU ids restricted to
   letters, digits, `-`, `.`, `_`. Rows with other ids are dropped; a file with many of them is rejected.
6. **Audit log**: every refusal is logged with a short hash, size and file name, never the content.

## Layers around the upload
| Layer | What it stops | Where |
|---|---|---|
| Content-Security-Policy | injected script loading code from, or sending data to, another website; framing | `layout.tsx` (production build); proven in a real browser |
| React output escaping | `<img onerror>` and similar in names, cities, chains, explanations | whole dashboard; tested in every tab |
| CSV export hardening | formulas that run when the exported file opens in Excel | `csvCell` |
| Security headers | sniffing, framing, caching of responses | API middleware |
| Request size limit, rate limit | huge bodies, floods of uploads (20 per minute per address) | API middleware |
| Roles | viewers cannot upload; made-up roles and headers are rejected | `security.py` |
| No dev login outside `local` | header "login" returns 501 in any other environment | tested |
| Four-eyes approval | one person (or one stolen session) cannot approve their own order | workflow |
| AI never decides | the model only phrases text; a guard rejects numbers that are not in the facts | `assistant/guard.py` |
| Dependency audit, static analysis, CodeQL | known-vulnerable packages and unsafe code patterns | `security.yml`, weekly |

## What about AI attacking it?
An attacker with an AI model faces the same layers as any other attacker; the AI does not
change what the server accepts. The parts that involve a model are designed so a manipulated
prompt cannot do harm:
- the dashboard assistant is deterministic (keyword routing to fixed, computed answers);
- the Bedrock explanation only phrases facts; its output is checked against those facts and
  falls back to a template;
- order quantities come from the forecasting and planning code, and a human approves them.
Prompt-injection attempts are part of the attack tests.

## What is NOT covered (be honest in an interview)
- **No third-party penetration test.** The attack tests are written and run by the project itself.
- **Not an antivirus engine.** Without ClamAV, unknown malware that looks like valid CSV is not "detected";
  it is simply never executed.
- **Cognito login is not built yet.** Outside `local` the API refuses everything (HTTP 501), which is safe
  but not usable. The role switch in the dashboard is a demo, not authentication.
- **The rate limit is per process and in memory.** A deployed API needs a WAF or API Gateway throttle in front.
- **The CSP allows inline scripts** because a static Next.js export needs them for start-up. A nonce-based
  policy needs a server. The policy still blocks other origins.
- **Response headers for the static site** (HSTS, `frame-ancestors`) must be set by the CDN; a meta tag cannot.
- **A compromised computer or browser** can always read what is on screen. Keep the system updated.
- **The demo is not deployed.** There is no public attack surface today.

## If you want it stronger next
Cognito + MFA, a CloudFront response-headers policy and AWS WAF, ClamAV or a managed S3 malware scan
in the upload path, nonce-based CSP behind a small server, an independent penetration test, and
secret scanning in CI.

## Added in v0.3.0

- Static server: CSP header with `frame-ancestors 'none'`, Permissions-Policy, COOP/CORP, request and header time limits against slow connections, URL length limit.
- API: at most two analyses at once (503 with Retry-After beyond that), so an upload flood cannot exhaust the processor; readiness probe.
- Damaged or hostile saved settings in the browser are ignored; one failing tab cannot take the dashboard down.
- Still true: no third-party penetration test, and no system is "unhackable".
