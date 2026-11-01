"""Feature builder: leakage safety and trading-day masking."""

import numpy as np
import pandas as pd
import pytest

from freshcast.features.builder import FEATURE_COLUMNS, build_features


def test_future_actuals_never_change_earlier_features(sales: pd.DataFrame) -> None:
    horizon = 2
    cutoff = pd.Timestamp("2025-04-01")
    base = build_features(sales, horizon)

    tampered = sales.copy()
    tampered["business_date"] = pd.to_datetime(tampered["business_date"])
    future = tampered["business_date"] >= cutoff
    tampered.loc[future, "units_sold"] = 9_999  # wildly different future demand
    changed = build_features(tampered, horizon)

    # Rows issued before the cutoff can only see data up to cutoff - 1.
    safe = base["business_date"] < cutoff + pd.Timedelta(days=horizon)
    cols = [c for c in FEATURE_COLUMNS if c.startswith(("lag_", "mean_"))]
    pd.testing.assert_frame_equal(base.loc[safe, cols], changed.loc[safe, cols])
    # ... and the tampering must actually matter later (test is not vacuous).
    assert not base.loc[~safe, cols].equals(changed.loc[~safe, cols])


def test_target_day_demand_is_not_a_feature(sales: pd.DataFrame) -> None:
    feats = build_features(sales, 2)
    for col in FEATURE_COLUMNS:
        if col in ("store_id", "sku"):
            continue
        corr = np.corrcoef(feats[col].fillna(0), feats["units_sold"])[0, 1]
        assert abs(corr) < 0.999, f"{col} looks like a copy of the target"


def test_lag7_matches_same_weekday_last_week(sales: pd.DataFrame) -> None:
    feats = build_features(sales, 2)
    one = feats[(feats["store_id"] == "DE-MUC-001") & (feats["sku"] == "MILK-1L")]
    one = one.set_index("business_date")
    day = pd.Timestamp("2025-03-12")  # Wednesday, previous Wednesday open
    assert one.loc[day, "lag_7"] == one.loc[day - pd.Timedelta(days=7), "units_sold"]


def test_closed_days_are_masked_in_lags(sales: pd.DataFrame) -> None:
    feats = build_features(sales, 2)
    # A Monday's lag_7 is last Monday; its lag_1-like neighbour Sunday is never used.
    sundays = feats[feats["dow"] == 6]
    assert sundays["is_open"].eq(False).all()
    monday_after_sunday_lag = feats[(feats["dow"] == 6)]["lag_7"]
    assert monday_after_sunday_lag.isna().all()  # last Sunday was closed -> NaN


def test_horizon_validation(sales: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="horizon"):
        build_features(sales, 0)
    with pytest.raises(ValueError, match="shorter"):
        build_features(sales, 10)
