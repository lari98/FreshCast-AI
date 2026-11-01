# FreshCast AI

Perishable & fresh-goods demand forecasting and waste-aware replenishment for
DACH retail, built as an AWS portfolio project.

> Status: **v0.1 in progress** - phase 1 (foundation, replenishment engine,
> event contract). Not a certified or legally reviewed product; all data is synthetic.

## Principles
- ML forecasts demand; deterministic rules compute orders; GenAI only explains.
- Incremental updates: a change to one store/SKU recomputes only that partition.
- Human approval before any order; food-safety holds always win.
- Evidence-based EU/DACH compliance claims (see `docs/compliance`).

## Quick start
```bash
cd packages/forecasting
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff format . && ruff check . && mypy && pytest
```

## Forecasting
Backtest: `python -m freshcast.models.backtest` (results in `docs/ml/`).

## API
See `docs/architecture/api.md`.

## Roadmap
1 Foundation (done) - 2 DACH demo data (done) - 3 API & DB (done) - 4 Forecast engine (done) -
5 Replenishment v2 (done) - 6 Incremental events (done) - 7 AWS & MLOps (code done, not deployed) -
8 Bedrock assistant - 9 Dashboard - 10 Security & release.
