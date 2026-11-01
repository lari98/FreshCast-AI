# Backtest results (synthetic data)

Forecast issued 2 days ahead; trading days only; rolling origins.

| Origin | WAPE baseline | WAPE LightGBM | MAE baseline | MAE LightGBM | Bias LightGBM | 80% interval coverage |
|---|---|---|---|---|---|---|
| 2025-09-11 | 17.8% | 11.2% | 9.28 | 5.86 | +1.6% | 71.4% |
| 2025-10-09 | 18.6% | 12.3% | 8.90 | 5.87 | +1.2% | 69.9% |
| 2025-11-06 | 19.1% | 12.9% | 8.53 | 5.75 | +2.4% | 71.8% |
| 2025-12-04 | 17.8% | 12.0% | 7.72 | 5.20 | +0.9% | 75.7% |
| **weighted mean** | 18.4% | 12.1% | 8.62 | 5.68 | +1.5% | 72.1% |

## LightGBM WAPE by SKU

| SKU | WAPE |
|---|---|
| MILK-1L | 8.6% |
| BREAD-WHEAT-750G | 10.2% |
| YOGURT-500G | 10.4% |
| TOMATO-500G | 13.0% |
| SALAD-MIXED-200G | 14.2% |
| CHICKEN-BREAST-500G | 15.6% |
| SALMON-FILLET-250G | 18.5% |
| STRAWBERRY-500G | 21.5% |

Data is simulated with Gaussian noise, so these numbers show the pipeline works and is leakage-safe; they do not predict real-world accuracy.
