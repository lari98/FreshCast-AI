# Benchmark (synthetic data, rolling-origin backtest)
| Metric | Seasonal naive | LightGBM |
|---|---|---|
| WAPE | 18.4 % | 12.1 % |
| 80 % interval coverage | – | about 72 % (too narrow) |

Synthetic data only: results show the pipeline works, not real-world accuracy.
Details: `docs/ml/backtest-results.md`, `docs/ml/model-card.md`.
