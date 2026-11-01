# API (phase 3)

Run locally (SQLite by default; PostgreSQL via `docker compose up -d db`):

```bash
cd apps/api
pip install -e ../../packages/forecasting -e ".[dev]"
export FRESHCAST_DATABASE_URL=postgresql+psycopg://freshcast:change-me-locally@localhost:5432/freshcast
alembic upgrade head
uvicorn --factory freshcast_api.main:app_factory --reload   # docs at /docs
```

| Endpoint | Role | Purpose |
|---|---|---|
| POST /v1/stock-lots | store_manager, admin | Receive a lot; writes outbox event + audit atomically |
| POST /v1/proposals | store_manager, admin | Compute an expiry-aware proposal from stored lots |
| POST /v1/proposals/{id}/approve | store_manager, admin | Four-eyes approval (creator cannot approve) |
| GET /v1/proposals/{id} | any role | Read a proposal |

Design points: transactional outbox with per store:sku monotonic versions;
append-only audit log; strict Pydantic validation (`extra="forbid"`); header
auth only when `FRESHCAST_ENV=local` (Cognito JWT in phase 7); no order is ever placed by the API.
