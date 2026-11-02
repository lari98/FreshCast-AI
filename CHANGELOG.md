# Changelog

## Unreleased (quality pass: speed, structure, features, palette)

- Full test and audit battery with written report: `docs/quality/test-report.md` (core 169 tests 96.36 %, API 48 tests 96.35 %, dashboard 133 tests, linters, mypy, Bandit, pip-audit, npm audit all clean).
- Speed: production-mode dashboard by default (`scripts/run-dashboard.ps1`, `-Dev` for hot reload), paged tables, memoisation, faster upload analysis.
- Structure: dashboard hooks and tab registry split out, replay reporting moved to `replay_report.py`, `clean_sales` split.
- Features: Today tab, quick search, audit trail with before/after values.
- Design: "Aubergine & Teal" palette with computed contrast (`docs/quality/design-tokens.md`).
- Security workflow runs static-server tests.

## Unreleased (security hardening and live update)
- Upload guard (`freshcast.security.upload_guard`): refuses disguised executables, archives, PDFs, Office files, images, scripts and markup payloads, NUL/control characters, oversized lines and columns, unsafe file names; cleans text cells (formula injection) and drops unsafe store/SKU ids; optional ClamAV scan that fails closed; refusals are logged without content.
- API: security headers, request size limit, in-memory rate limit (uploads 20/min per address), upload checks on sales and stock files.
- Dashboard: Content-Security-Policy (production build), browser-side upload check, automatic update watcher (`version.json`): a new deployment reloads the open tab, settings and approvals are kept, uploaded data is never reloaded away.
- `scripts/run-dashboard.ps1`: stops an old server on the port and mirrors the repository every 2 seconds, so a `git pull` shows up in the open tab by hot reload.
- Attack tests in phases (`docs/security/attack-testing.md`), `security.yml` workflow (pip-audit, npm audit, Bandit, CodeQL, attack tests, weekly). Found and fixed a 500 error on header-only uploads.
- `docs/security/how-freshcast-is-protected.md`: what is protected and what is not.

## Unreleased (retail chains and market map)
- Retail chain (Handelskette) as a second dimension next to the market: header switch, Settings checkboxes, upload column `chain` (aliases `Handelskette`, `Kette`, `retailer`, `banner`).
- New *Marktkarte* tab: chain x country matrix (store count, items, loss ratio); the same chain can be compared across DE, AT and CH; a click filters to one chain in one country.
- Demo data now covers all seven stores (56 items) with three fictional chains (MarktHaus, PreisPunkt, AlpenFrisch); no real company is shown with synthetic numbers.
- `replay.json` stores market x chain x policy raw sums (`segments`); the Savings tab recomputes ratios from sums for the active filter.
- `scripts/run-dashboard.ps1` refreshes the Windows copy and starts the dashboard; a version footer shows the build, so an old copy is easy to spot.
- `docs/data/market-chains.md`: how chains and markets fit together, with real DACH chains as orientation only.

## Unreleased (phase 13)
- Market and currency filter: show Germany, Austria and Switzerland (or any combination, EUR and/or CHF) across all tabs; header presets, Settings checkboxes, saved in the browser. The Savings replay is now split by market.
- Dashboard redesign: new light/dark palette with a theme switch, grouped sidebar navigation (17 sections), settings for the cost share.
- Approval tab with the four-eyes principle: planner edits a quantity (whole packs, reason required) and submits, reviewer approves or rejects; state kept in the browser (demo, not authentication).
- Store comparison, markdown (price cut) what-if for expiring stock with stated assumptions, help and glossary.
- Newsvendor (critical-ratio) order target with a per-SKU overage factor estimated on data before the evaluation window.
- Policy replay: naive, v1 rule, newsvendor and planner played day by day over 3 months with FEFO, walk-forward models and a stock-conservation test. Report in `docs/ml/policy-replay.md`, ADR 0004.
- Dashboard: Savings tab (policy comparison, waste per week, product groups) fed by `replay.json`. Synthetic data, assumed costs, not evidence of real savings.

## Unreleased (advanced dashboard)
- Seven-tab dashboard: Overview (KPIs per currency, attention list, waste ranking), Orders (search, sort, multi-select approval, CSV export of approved lines with a formula-injection guard), Forecast (chart, proposal, out-of-sample accuracy), Expiry radar (rule-based hints, labelled as not an AI decision), What-if (demand and safety-stock sliders), Data (upload and quality), Model (backtest and scale facts, labelled synthetic).
- Store scope for all tabs, tab in the URL hash, ARIA tabs with keyboard support, axe test per tab.
- Four more tabs: Weekly plan (7-day forecast heatmap), Alerts (rule-based stock-out, expiry, demand-spike and accuracy warnings), Assistant (fixed questions answered from the loaded data; not a language model, so numbers cannot be invented), Categories (forecast, revenue and waste rate per product group).
- Demo and upload payloads carry unit price and category.

## Unreleased (phase 12)
- Upload your own sales/stock CSV (German Excel formats supported) and get forecasts, proposals and a data-quality report: `POST /v1/analyze`, dashboard upload panel, sample files.
- `scripts/run-api.ps1` starts the API locally on Windows.

## Unreleased (phase 11)
- Conformalised quantile regression (per-SKU) for calibrated 80 % intervals: coverage 72.1 % to 80.9 % in the synthetic backtest.
- Vectorised rolling features (no per-series Python call); verified identical to the pandas reference.
- Scale benchmark: 50,000 series, features 8.6 s + prediction 0.8 s per daily run on 2 vCPUs; training 79 s for 20,000 series (`docs/ml/scale-benchmark.md`).

## v0.1.0 – first portfolio release
- Expiry-aware replenishment engine and FEFO planner (EU/DACH synthetic data).
- Leakage-safe LightGBM forecasting with baseline gate and backtest.
- Versioned event pipeline with outbox, idempotent worker, DLQ and replay.
- FastAPI service with RBAC, four-eyes approval and audit log.
- AWS CDK stacks (not deployed), grounded Bedrock explanations with number guard.
- Next.js DE/EN dashboard with accessible chart, demo data and axe test.
- Known gaps: see `docs/security/review-v0.1.0.md`.
