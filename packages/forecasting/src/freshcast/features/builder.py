"""Leakage-safe feature engineering for daily store/SKU demand.

Leakage rule
------------
A row for target day ``t`` may only use *demand* observed on or before
``t - horizon`` (the moment the forecast is issued). Demand lags and rolling
statistics are therefore shifted by at least ``horizon`` days. Calendar,
holiday, promotion and price columns are plans known in advance, so using the
value for day ``t`` itself is legitimate.

Closed days (Sundays, holidays) carry no demand signal; their demand is masked
to NaN so lags and rolling means describe *trading* days only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

KEYS = ["store_id", "sku"]
LAGS = (7, 14, 28)
WINDOWS = (7, 28)

FEATURE_COLUMNS: list[str] = [
    "store_id",
    "sku",
    "dow",
    "month",
    "doy_sin",
    "doy_cos",
    "is_holiday",
    "is_promo",
    "unit_price",
    *[f"lag_{k}" for k in LAGS],
    *[f"mean_{w}" for w in WINDOWS],
]


def build_features(sales: pd.DataFrame, horizon: int = 2) -> pd.DataFrame:
    """Return ``sales`` plus features for a forecast issued ``horizon`` days ahead."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    too_short = [k for k in LAGS if k < horizon]
    if too_short:
        raise ValueError(f"lags {too_short} are shorter than horizon {horizon}")

    df = sales.copy()
    df["business_date"] = pd.to_datetime(df["business_date"])
    df = df.sort_values([*KEYS, "business_date"]).reset_index(drop=True)

    # Demand on trading days only; NaN elsewhere so closed days do not pollute stats.
    demand = df["units_sold"].where(df["is_open"].astype(bool))
    grouped = demand.groupby([df["store_id"], df["sku"]])

    for k in LAGS:
        df[f"lag_{k}"] = grouped.shift(k)
    for w in WINDOWS:
        # shift(horizon) first: the window must end at the forecast issue date.
        df[f"mean_{w}"] = grouped.transform(
            lambda s, w=w: s.shift(horizon).rolling(w, min_periods=1).mean()
        )

    dates = df["business_date"]
    doy = dates.dt.day_of_year.to_numpy()
    df["dow"] = dates.dt.day_of_week
    df["month"] = dates.dt.month
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    for flag in ("is_holiday", "is_promo"):
        df[flag] = df[flag].astype(int)
    df["is_open"] = df["is_open"].astype(bool)
    return df
