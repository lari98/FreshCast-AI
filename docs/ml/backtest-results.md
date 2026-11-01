# Backtest results (synthetic data)

Forecast issued 2 days ahead; trading days only; rolling origins.

| Origin | WAPE baseline | WAPE LightGBM | MAE baseline | MAE LightGBM | Bias LightGBM | 80% interval coverage |
|---|---|---|---|---|---|---|
| 2025-09-11 | 17.8% | 11.6% | 9.28 | 6.02 | +1.7% | 82.3% |
| 2025-10-09 | 18.6% | 12.7% | 8.90 | 6.08 | +2.2% | 78.9% |
| 2025-11-06 | 19.1% | 13.4% | 8.53 | 5.97 | +3.5% | 78.0% |
| 2025-12-04 | 17.8% | 12.8% | 7.72 | 5.53 | +2.9% | 85.0% |
| **weighted mean** | 18.4% | 12.6% | 8.62 | 5.91 | +2.6% | 80.9% |

## LightGBM WAPE by SKU

| SKU | WAPE |
|---|---|
| MILK-1L | 8.6% |
| BREAD-WHEAT-750G | 10.3% |
| YOGURT-500G | 10.6% |
| TOMATO-500G | 13.1% |
| SALAD-MIXED-200G | 14.5% |
| CHICKEN-BREAST-500G | 15.7% |
| SALMON-FILLET-250G | 18.6% |
| STRAWBERRY-500G | 27.8% |

Data is simulated with Gaussian noise, so these numbers show the pipeline works and is leakage-safe; they do not predict real-world accuracy.
