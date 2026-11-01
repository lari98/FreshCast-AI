# Changelog

## Unreleased (advanced dashboard)
- Seven-tab dashboard: Overview (KPIs per currency, attention list, waste ranking), Orders (search, sort, multi-select approval, CSV export of approved lines with a formula-injection guard), Forecast (chart, proposal, out-of-sample accuracy), Expiry radar (rule-based hints, labelled as not an AI decision), What-if (demand and safety-stock sliders), Data (upload and quality), Model (backtest and scale facts, labelled synthetic).
- Store scope for all tabs, tab in the URL hash, ARIA tabs with keyboard support, axe test per tab.
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
