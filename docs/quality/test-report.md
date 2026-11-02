# Quality and test report

Run date: 2026-11-02. Environment: Linux container, Python 3.12, Node 22.
All data is synthetic; chain names are fictional. Nothing here is a certification.

## Results

| Suite | Result |
|---|---|
| Core package (`packages/forecasting`) pytest | 169 passed, line coverage 96.36 % (gate 85 %) |
| API (`apps/api`) pytest | 48 passed, line coverage 96.35 % (gate 85 %) |
| ruff check and format, both Python packages | clean |
| mypy strict, both packages | clean |
| Bandit, both packages | no findings |
| Dashboard `tsc --noEmit` | clean |
| Dashboard ESLint | clean |
| Dashboard vitest (6 files) | 133 passed, includes axe-core checks |
| Static server (node:test) | 3 passed |
| Production build (Next.js static export) | succeeds |
| `pip-audit` | no known vulnerabilities |
| `npm audit --omit=dev` | 0 vulnerabilities |

## Security attack tests

Phased tests live in `packages/forecasting/tests/security`, `apps/api/tests/test_security_phase2_api.py`
and `apps/dashboard/tests/security.test.tsx`. They cover hostile uploads (magic bytes, NUL and control
characters, script payloads, formula injection, bad filenames), API limits (413, rate limit, headers),
CSP, prompt-injection text in data, and the update watcher. All pass. See `docs/security/`.

## Performance

Measured with Playwright against the same build:

| Measurement | Before | After |
|---|---|---|
| First load, dev server | 11.4 s | (production mode default) 0.3 to 0.6 s |
| Tab switch, average | not recorded | about 85 ms |
| Verfall tab, 336 items | 405 ms | 130 ms |
| Freigabe tab, 336 items | 342 ms | 144 ms |

Causes fixed: unpaged long tables (new `PagedRows`), repeated recomputation (memoisation), and running
the dev server by default (now `scripts/run-dashboard.ps1` serves the production build; `-Dev` gives hot reload).
Backend hot spots in `byod/analyze.py` and `byod/ingest.py` were reduced (grouped dictionaries instead of repeated
frame filters, cached calendar flags).

## Structural changes

`Dashboard.tsx` split into hooks (`useSettings`, `useHashTab`) and `lib/tabs.ts`; replay reporting moved to
`replenishment/replay_report.py`; `clean_sales` split into three functions; upload guard control-byte count simplified.

## New features

Today tab (prioritised task list), quick search (command palette), audit trail with before/after values,
paged tables, rewritten palette (see `design-tokens.md`).

## Known limits (honest)

- Frontend line coverage is not measured; component tests and axe checks exist.
- `infrastructure/cdk` tests were not run here (`aws_cdk` not installed in this environment); CI runs them.
- No third-party penetration test. The system is hardened and attack-tested, not "unhackable".
- No deployed AWS environment was exercised.
- Replay results use synthetic data and assumed cost shares (60 % / 40 %); they are not real savings.
- Loss ratio can exceed 100 % in the map (waste value relative to revenue); the map hint explains this.

## Re-run for v0.3.0 (2026-11-02)

| Suite | Result |
|---|---|
| Core pytest | 170 passed, coverage 96.38 % |
| API pytest | 55 passed, coverage 96.52 % |
| Dashboard vitest | 145 passed (7 files) |
| Static server (node:test) | 5 passed |
| ruff, ruff format, mypy strict, Bandit | clean |
| tsc, ESLint | clean |
| `pip-audit`, `npm audit --omit=dev` | no known vulnerabilities, 0 vulnerabilities |

Efficiency measurements: see `efficiency.md`.
