# Changelog

## v0.1.0 – first portfolio release
- Expiry-aware replenishment engine and FEFO planner (EU/DACH synthetic data).
- Leakage-safe LightGBM forecasting with baseline gate and backtest.
- Versioned event pipeline with outbox, idempotent worker, DLQ and replay.
- FastAPI service with RBAC, four-eyes approval and audit log.
- AWS CDK stacks (not deployed), grounded Bedrock explanations with number guard.
- Next.js DE/EN dashboard with accessible chart, demo data and axe test.
- Known gaps: see `docs/security/review-v0.1.0.md`.
