"""LightGBM point and quantile forecaster.

Three models share one feature set: a mean model (point forecast) and two
quantile models (default 10 % / 90 %) that give an 80 % prediction interval.
Closed days are not modelled; they are forecast as zero by business rule.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from freshcast.features.builder import FEATURE_COLUMNS

CATEGORICAL = ["store_id", "sku"]
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

    def __init__(self, lower_q: float = 0.1, upper_q: float = 0.9) -> None:
        """Configure the quantiles that bound the prediction interval."""
        if not 0 < lower_q < 0.5 < upper_q < 1:
            raise ValueError("require 0 < lower_q < 0.5 < upper_q < 1")
        self._lower_q, self._upper_q = lower_q, upper_q
        self._categories: dict[str, pd.Index] = {}
        self._point = LGBMRegressor(**_PARAMS)
        self._lower = LGBMRegressor(objective="quantile", alpha=lower_q, **_PARAMS)
        self._upper = LGBMRegressor(objective="quantile", alpha=upper_q, **_PARAMS)

    def _matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        x = df[FEATURE_COLUMNS].copy()
        for col in CATEGORICAL:
            x[col] = pd.Categorical(x[col], categories=self._categories[col])
        return x

    def fit(self, features: pd.DataFrame) -> DemandForecaster:
        """Train on open days only."""
        train = features[features["is_open"]]
        if train.empty:
            raise ValueError("no trading-day rows to train on")
        self._categories = {c: pd.Index(sorted(train[c].unique())) for c in CATEGORICAL}
        x, y = self._matrix(train), train["units_sold"]
        for model in (self._point, self._lower, self._upper):
            model.fit(x, y)
        return self

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return columns ``point``, ``lower``, ``upper`` (zero on closed days)."""
        if not self._categories:
            raise RuntimeError("model is not fitted")
        x = self._matrix(features)
        point = np.clip(self._point.predict(x), 0, None)
        # Enforce lower <= point <= upper (separately trained quantiles can cross).
        lower = np.minimum(np.clip(self._lower.predict(x), 0, None), point)
        upper = np.maximum(self._upper.predict(x), point)
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


def safety_stock_units(point: float, upper: float) -> int:
    """Safety stock = headroom between the point forecast and the upper quantile.

    This is the bridge to the replenishment engine's ``safety_stock_units``.
    """
    return max(0, math.ceil(upper - point))
