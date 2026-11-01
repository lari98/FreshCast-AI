# Changelog

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
