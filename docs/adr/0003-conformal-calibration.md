# ADR 0003: Conformal calibration of prediction intervals

Status: accepted (phase 11)

Context: raw quantile models covered only 72 % of outcomes for an 80 % interval, which makes safety stock too small.

Decision: use split conformalised quantile regression, holding out the latest 28 days, with a per-SKU correction when at least 30 calibration rows exist, otherwise a global one.

Consequences: coverage is close to nominal (80.9 %). Cost: the model does not train on the latest 28 days (about 0.5 points of WAPE). Under drift the guarantee weakens, so coverage is monitored in the backtest. Calibration data must stay out of training (enforced by the date split).
