# Benchmark (synthetic data, rolling-origin backtest)
| Metric | Seasonal naive | LightGBM |
|---|---|---|
| WAPE | 18.4 % | 12.6 % (with 28-day calibration hold-out; 12.1 % without) |
| 80 % interval coverage | – | 80.9 % calibrated (72.1 % before calibration) |

Synthetic data only: results show the pipeline works, not real-world accuracy.
Details: `docs/ml/backtest-results.md`, `docs/ml/model-card.md`.
