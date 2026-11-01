"""Conformal calibration, vectorised features and the scale benchmark."""

import numpy as np
import pandas as pd
import pytest

from freshcast.benchmark.scale import generate_series, measure, render
from freshcast.features.builder import WINDOWS, build_features
from freshcast.models.lgbm import DemandForecaster, _conformal_quantile
from freshcast.models.metrics import interval_coverage


def test_conformal_quantile_is_finite_sample_corrected() -> None:
    scores = np.arange(1.0, 10.0)  # 9 scores
    # alpha=0.2 -> ceil(10 * 0.8)/9 = 8/9 -> 8th smallest... method "higher" -> 9.0
    assert _conformal_quantile(scores, 0.2) >= 8.0
    assert _conformal_quantile(scores, 0.0001) == 9.0  # cannot exceed the maximum


def test_calibration_improves_coverage(sales: pd.DataFrame) -> None:
    feats = build_features(sales, 2)
    cut = pd.Timestamp("2025-06-01")
    train, test = (
        feats[feats["business_date"] < cut],
        feats[(feats["business_date"] >= cut) & feats["is_open"]],
    )
    y = test["units_sold"].to_numpy(dtype=np.float64)

    def coverage(model: DemandForecaster) -> float:
        p = model.fit(train).predict(test)
        return interval_coverage(y, p["lower"].to_numpy(), p["upper"].to_numpy())

    raw = coverage(DemandForecaster())
    calibrated = coverage(DemandForecaster(calibration_days=28))
    assert calibrated > raw


def test_calibration_guards(sales: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="calibration_days"):
        DemandForecaster(calibration_days=-1)
    feats = build_features(sales, 2)
    short = feats[
        feats["business_date"] < feats["business_date"].min() + pd.Timedelta(days=5)
    ]
    with pytest.raises(ValueError, match="too short"):
        DemandForecaster(calibration_days=60).fit(short)


def test_vectorised_rolling_means_match_pandas_rolling(sales: pd.DataFrame) -> None:
    new = build_features(sales, 2)
    df = sales.sort_values(["store_id", "sku", "business_date"]).reset_index(drop=True)
    demand = df["units_sold"].where(df["is_open"].astype(bool))
    grouped = demand.groupby([df["store_id"], df["sku"]])
    for w in WINDOWS:
        ref = grouped.transform(
            lambda s, w=w: s.shift(2).rolling(w, min_periods=1).mean()
        )
        np.testing.assert_allclose(
            new[f"mean_{w}"].to_numpy(), ref.to_numpy(), equal_nan=True, atol=1e-9
        )


def test_scale_generator_shape_and_closed_sundays() -> None:
    df = generate_series(30, days=14)
    assert len(df) == 30 * 14
    assert df.groupby(["store_id", "sku"]).ngroups == 30
    sundays = pd.to_datetime(df["business_date"]).dt.day_of_week == 6
    assert not df.loc[sundays, "is_open"].any()


def test_measure_and_render_small() -> None:
    result, model = measure(40, days=60)
    assert model is not None and result.train_s is not None
    reuse, _ = measure(80, days=60, train=False, model=model)
    text = render([result, reuse], "test")
    assert "reused model" in text and "| 40 |" in text
    with pytest.raises(ValueError, match="fitted model"):
        measure(10, days=40, train=False)
