# Bring your own data (phase 12)

Upload a sales CSV (and optionally a stock CSV) in the dashboard. The API
validates it, trains a model on it and returns forecasts, order proposals and a
data-quality report. `POST /v1/analyze` (roles: store_manager, admin).

## Sales file (required columns)
| Column | German alias | Notes |
|---|---|---|
| store_id | Filiale, Markt | `DE-`, `AT-`, `CH-` prefix selects the holiday calendar and currency |
| sku | Artikelnummer | |
| business_date | Datum | `yyyy-mm-dd`, `dd.mm.yyyy`, `dd/mm/yyyy` (one format per file) |
| units_sold | Menge, Absatz | whole units; negatives dropped, fractions rounded |

Optional: `product_name` (Artikelname), `unit_price` (Preis), `shelf_life_days` (Haltbarkeit_Tage, default 5), `pack_size` (Gebindegroesse, default 1).

## Stock file (optional)
`store_id, sku, quantity (Bestand), use_by_date (MHD)`, optional `lot_id (Charge)`. Without it, shelves are assumed empty and the report says so.

## What happens
1. Read: UTF-8 (with BOM) or Latin-1, separator `;` `,` or tab, decimal comma, German headers.
2. Validate and repair, every change reported: unreadable/negative rows dropped, duplicates summed, missing trading days filled with 0 (may hide stock-outs), series with under 60 days or no recent sales skipped.
3. Forecast: leakage-safe features; a *history* model (trained before the last 14 days, so the chart's actual-vs-forecast is out of sample) and a *current* model for the next 7 days. Intervals are conformally calibrated when at least 120 days exist.
4. Plan: FEFO planner with the stock lots. Assumptions printed with the result: unit cost 60 % and margin 40 % of price, 1-day lead time, delivery Monday to Saturday.

## Limits and privacy
25 MB, 500,000 rows, 300 series per upload. Files are processed in memory, not stored; only counts are logged, never row contents. For larger data use the batch pipeline.

## Run it locally (Windows)
1. `.\scripts\run-api.ps1` (Python 3.12+; creates `C:\dev\venv-freshcast`).
2. In another window run the dashboard (see `dashboard.md`) and open http://localhost:3000.
3. Try `data/samples/beispiel_absatz.csv` and `beispiel_bestand.csv` (German Excel style).

## Known gaps
Sign-in is header-based in local mode only. Promotions are not read from the upload, regional holidays are not modelled, and a stock-out hides true demand. Results depend on how representative your history is; check the data-quality panel first.
