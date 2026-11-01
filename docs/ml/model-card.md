# Model card: FreshCast demand forecaster v0.1

**Intended use:** day-level unit demand forecast per store and SKU for fresh
goods, feeding a *human-approved* replenishment proposal. Not for staffing,
pricing of individuals, or any automated purchase or disposal of food.

**Model:** LightGBM mean model plus 10 % / 90 % quantile models (80 % interval).
Benchmark: seasonal naive (same weekday last week, 28-day mean fallback).

**Features:** weekday, month, annual seasonality, holiday, promotion, price,
store, SKU, demand lags (7/14/28 days) and rolling means (7/28 days), all lagged
by at least the forecast horizon (2 days). Closed days are forecast as zero by rule.

**Data:** fully synthetic (see `docs/data/synthetic-data.md`); no personal data.

**Evaluation:** rolling-origin backtest, 4 folds x 28 days, trading days only
(`docs/ml/backtest-results.md`). On synthetic data LightGBM reduces WAPE from
about 18 % (baseline) to about 12 %, with +1.5 % bias.

**Known limitations**
- Prediction intervals are too narrow: about 72 % coverage versus 80 % nominal.
  Do not size safety stock from them without calibration (e.g. conformal).
- Accuracy on real retail data is unknown; synthetic noise is Gaussian and
  the generator's patterns are simple.
- Strawberries (strong seasonality) are the weakest SKU (about 21 % WAPE).
- No new-product (cold-start), stock-out censoring or weather features yet.

**Oversight and governance:** a manager approves every order (four-eyes rule);
food-safety holds and recalls override any forecast. Retrain and re-evaluate
before any change is promoted; the baseline must be beaten on the same folds.
