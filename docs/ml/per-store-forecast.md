# Per-store training and forecast cache

`freshcast.byod.analyze.analyze(..., per_store=True)` (or `FRESHCAST_PER_STORE=1`) trains a history model and a current model **per store**.
Each group's result is stored in `freshcast.byod.forecast_cache.FORECASTS`, keyed by a SHA-256 over the group's feature rows, the as-of date,
the calibration setting and `MODEL_VERSION` (raise it when model or features change). Entries live in memory, at most 64, for one hour, and a hit needs
byte-identical data.

## Benchmark (synthetic, `data/samples/large`: 3 stores, 100 SKUs, 1,400 held-out store-SKU-days with ground truth)

| Mode | WAPE | Coverage of 10-90 % interval | Time |
|---|---|---|---|
| Shared model (default) | 0.2713 | 82.1 % | 33.0 s |
| Per store, cold | 0.2769 | 79.4 % | 37.0 s |
| Per store, one of three stores changed | same as cold | same | 14.5 s |

Reading: per-store is 2 % worse in WAPE and slower cold, but 56 % faster when only one store changed. Use it for chains that re-upload daily;
keep the shared model for single uploads. Reproduce: `python scripts/bench_per_store.py`.
