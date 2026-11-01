"""LightGBM point and quantile forecaster.

Three models share one feature set: a mean model (point forecast) and two
quantile models (default 10 % / 90 %) that give an 80 % prediction interval.
Closed days are not modelled; they are forecast as zero by business rule.

Calibration
-----------
Raw quantile models are usually too narrow. With ``calibration_days > 0`` the
most recent days are held out of training and used for *conformalised quantile
regression* (CQR, Romano et al. 2019): the interval is widened by the
finite-sample-corrected quantile of the conformity scores, per SKU where enough
calibration rows exist (Mondrian conformal), else globally. Under
exchangeability this gives at least ``upper_q - lower_q`` coverage on average.
Demand is not perfectly exchangeable over time, so coverage is *measured* in
the backtest rather than assumed.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from freshcast.features.builder import FEATURE_COLUMNS

CATEGORICAL = ["store_id", "sku"]
_MIN_GROUP = 30  # minimum calibration rows for a per-SKU (Mondrian) correction
_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.9,
    "random_state": 42,
    "deterministic": True,
    "force_row_wise": True,
    "n_jobs": 1,
    "verbose": -1,
}


class DemandForecaster:
    """Fit on trading-day rows; predict point forecast and interval."""

    def __init__(
        self,
        lower_q: float = 0.1,
        upper_q: float = 0.9,
        calibration_days: int = 0,
        n_jobs: int = 1,
    ) -> None:
        """Configure interval quantiles, conformal calibration and threads."""
        if not 0 < lower_q < 0.5 < upper_q < 1:
            raise ValueError("require 0 < lower_q < 0.5 < upper_q < 1")
        if calibration_days < 0:
            raise ValueError("calibration_days must be >= 0")
        self._lower_q, self._upper_q = lower_q, upper_q
        self._calibration_days = calibration_days
        self._categories: dict[str, pd.Index] = {}
        params = {**_PARAMS, "n_jobs": n_jobs}
        self._point = LGBMRegressor(**params)
        self._lower = LGBMRegressor(objective="quantile", alpha=lower_q, **params)
        self._upper = LGBMRegressor(objective="quantile", alpha=upper_q, **params)
        self._global_shift = 0.0
        self._sku_shift: dict[str, float] = {}

    def _matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        x = df[FEATURE_COLUMNS].copy()
        for col in CATEGORICAL:
            x[col] = pd.Categorical(x[col], categories=self._categories[col])
        return x

    def fit(self, features: pd.DataFrame) -> DemandForecaster:
        """Train on open days; calibrate the interval on the latest days if enabled."""
        open_rows = features[features["is_open"]]
        if open_rows.empty:
            raise ValueError("no trading-day rows to train on")
        train, calib = open_rows, open_rows.iloc[0:0]
        if self._calibration_days:
            cutoff = open_rows["business_date"].max() - pd.Timedelta(
                days=self._calibration_days
            )
            train = open_rows[open_rows["business_date"] <= cutoff]
            calib = open_rows[open_rows["business_date"] > cutoff]
            if train.empty or calib.empty:
                raise ValueError("history too short for the calibration window")
        self._categories = {c: pd.Index(sorted(train[c].unique())) for c in CATEGORICAL}
        x, y = self._matrix(train), train["units_sold"]
        for model in (self._point, self._lower, self._upper):
            model.fit(x, y)
        self._calibrate(calib)
        return self

    def _calibrate(self, calib: pd.DataFrame) -> None:
        """Compute CQR interval widening from held-out rows (no-op if empty)."""
        self._global_shift, self._sku_shift = 0.0, {}
        if calib.empty:
            return
        raw = self._raw_interval(calib)
        y = calib["units_sold"].to_numpy(dtype=np.float64)
        scores = np.maximum(raw[0] - y, y - raw[1])
        self._global_shift = _conformal_quantile(scores, self._alpha)
        skus = calib["sku"].to_numpy()
        for sku in np.unique(skus):
            group = scores[skus == sku]
            if len(group) >= _MIN_GROUP:
                self._sku_shift[str(sku)] = _conformal_quantile(group, self._alpha)

    @property
    def _alpha(self) -> float:
        return 1.0 - (self._upper_q - self._lower_q)

    def _raw_interval(self, features: pd.DataFrame) -> tuple[Any, Any]:
        x = self._matrix(features)
        return self._lower.predict(x), self._upper.predict(x)

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return columns ``point``, ``lower``, ``upper`` (zero on closed days)."""
        if not self._categories:
            raise RuntimeError("model is not fitted")
        x = self._matrix(features)
        point = np.clip(self._point.predict(x), 0, None)
        # Enforce lower <= point <= upper (separately trained quantiles can cross).
        raw_lower, raw_upper = self._lower.predict(x), self._upper.predict(x)
        shift = np.array(
            [self._sku_shift.get(str(k), self._global_shift) for k in features["sku"]]
        )
        lower = np.minimum(np.clip(raw_lower - shift, 0, None), point)
        upper = np.maximum(raw_upper + shift, point)
        open_mask = features["is_open"].to_numpy()
        out = pd.DataFrame(
            {
                "point": np.where(open_mask, point, 0.0),
                "lower": np.where(open_mask, lower, 0.0),
                "upper": np.where(open_mask, upper, 0.0),
            },
            index=features.index,
        )
        return out


def _conformal_quantile(scores: Any, alpha: float) -> float:
    """Finite-sample-corrected (1 - alpha) quantile of conformity scores."""
    n = len(scores)
    level = min(1.0, math.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


def safety_stock_units(point: float, upper: float) -> int:
    """Safety stock = headroom between the point forecast and the upper quantile.

    This is the bridge to the replenishment engine's ``safety_stock_units``.
    """
    return max(0, math.ceil(upper - point))
