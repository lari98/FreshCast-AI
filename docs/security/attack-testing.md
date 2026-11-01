# Attack testing (phases)

Each phase attacks one layer. All tests run in CI (`.github/workflows/security.yml`) and on every
`pytest` / `npm test`. A test that passes means the attack was **refused or neutralised**.
These are the project's own tests, not an independent penetration test.

| Phase | Target | Attacks | Tests |
|---|---|---|---|
| 1 | CSV intake (Python) | executables, ELF, ZIP/Office/JAR, PDF, legacy Office, gzip, shell scripts and images renamed `.csv`, including behind a BOM; NUL bytes and control characters; `<script>`, `<?php`, `<iframe>`, `<img onerror>`, `javascript:`; 100,000-character lines; 150 columns; path traversal and double extensions in file names; spreadsheet formula injection in names, categories and chains; unsafe store/SKU ids; empty and header-only files; scanner protocol with the standard antivirus test string; scanner down (fail closed); logs without content | `packages/forecasting/tests/security/` |
| 2 | HTTP API | hostile uploads (422 with reason); stock file checked like sales; scanner unreachable; security headers; dev login outside `local` (501); role spoofing; viewer upload (403); 10 GB `Content-Length` and negative length (413); upload flood (429 after 20/min); foreign CORS origin; SQL-injection style ids | `apps/api/tests/test_security_phase2_api.py` |
| 3 | Dashboard | script and markup payloads in item names, cities, chains and explanations rendered in all 18 tabs (no element created, no handler, no code run); disguised executables and oversize files stopped before any request; CSV export formulas | `apps/dashboard/tests/security.test.tsx` |
| 4 | Assistant (prompt injection) | "ignore previous instructions", fake `SYSTEM:` messages, requests for secrets or huge orders: answers come only from loaded data and nothing changes in the approval workflow | `security.test.tsx`, `packages/forecasting/tests/test_assistant.py` |
| 5 | Update channel | a new-build file triggers a reload; malformed, missing or hostile `version.json` is ignored; uploaded data is never reloaded away | `security.test.tsx` |
| 6 | Supply chain | known-vulnerable Python and npm packages, unsafe code patterns | `pip-audit`, `npm audit`, Bandit, CodeQL (`security.yml`, weekly) |
| 7 | Real browser | production build: injected `fetch` to another site, script from another site and a foreign iframe are blocked by the CSP; a changed `version.json` reloads the open tab and keeps the selected tab | one-off Playwright run (result below) |

## Result of the last run (2026-11-01)
- Phase 1: 43 tests pass. Phase 2: 21 tests pass. Phases 3 to 5: 32 tests pass.
- Phase 6: pip-audit "no known vulnerabilities"; npm audit 0 vulnerabilities; Bandit clean.
- Phase 7 (Chromium): `fetch` to another site: blocked; external script: blocked; foreign iframe: blocked
  ("Framing ... violates ... default-src"); after the version file changed, the open page reloaded by
  itself within 5 seconds and stayed on the same tab.

## A real bug these tests found
A header-only CSV made the new id check crash with a 500 error (a pandas typing problem on empty data).
It is fixed and has its own test (`test_header_only_and_empty_files_give_a_clean_error`).

## Run them yourself
```
cd packages/forecasting && pytest tests/security
cd apps/api            && pytest tests/test_security_phase2_api.py
cd apps/dashboard      && npx vitest run tests/security.test.tsx
```
The antivirus test string used in phase 1 is the harmless industry-standard EICAR text. It is assembled
at run time so that no antivirus product on your computer flags the repository itself.

## Not yet tested
Fuzzing the parser at scale, load tests of the rate limiter behind a real proxy, a deployed WAF,
authentication flows (Cognito does not exist yet), and anything on a deployed environment.
