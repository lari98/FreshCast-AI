"""Seasonal-naive benchmark: demand equals the same weekday last week.

If that value is missing (e.g. the day was a holiday) the 28-day trading-day
mean is used. Any model must beat this benchmark to be worth deploying.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def seasonal_naive(features: pd.DataFrame) -> pd.Series[float]:
    """Return baseline forecasts; closed days are forecast as zero."""
    forecast = features["lag_7"].fillna(features["mean_28"]).fillna(0.0)
    return pd.Series(np.where(features["is_open"], forecast, 0.0), index=features.index)
