"""Metrics, baseline, LightGBM forecaster and backtest."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from freshcast.features.builder import build_features
from freshcast.models.backtest import render_report, run_backtest
from freshcast.models.baseline import seasonal_naive
from freshcast.models.lgbm import DemandForecaster, safety_stock_units
from freshcast.models.metrics import bias, interval_coverage, mae, wape

A = np.array([10.0, 20.0, 30.0])


def test_metrics_known_values() -> None:
    f = np.array([12.0, 18.0, 33.0])
    assert wape(A, f) == pytest.approx(7 / 60)
    assert mae(A, f) == pytest.approx(7 / 3)
    assert bias(A, f) == pytest.approx(3 / 60)
    assert interval_coverage(A, A - 1, A + 1) == 1.0
    assert interval_coverage(A, A + 1, A + 2) == 0.0


def test_metrics_reject_zero_demand() -> None:
    zeros = np.zeros(3)
    with pytest.raises(ValueError, match="WAPE"):
        wape(zeros, zeros)
    with pytest.raises(ValueError, match="bias"):
        bias(zeros, zeros)


def test_baseline_zero_when_closed(sales: pd.DataFrame) -> None:
    feats = build_features(sales, 2)
    base = seasonal_naive(feats)
    assert (base[~feats["is_open"]] == 0).all()
    assert (base[feats["is_open"]] >= 0).all()


@pytest.fixture(scope="module")
def fitted(sales: pd.DataFrame) -> tuple[DemandForecaster, pd.DataFrame]:
    feats = build_features(sales, 2)
    cut = pd.Timestamp("2025-06-01")
    model = DemandForecaster().fit(feats[feats["business_date"] < cut])
    return model, feats[feats["business_date"] >= cut]


def test_forecaster_output_is_ordered_and_zero_when_closed(
    fitted: tuple[DemandForecaster, pd.DataFrame],
) -> None:
    model, test = fitted
    pred = model.predict(test)
    assert len(pred) == len(test)
    assert (pred["lower"] <= pred["point"]).all()
    assert (pred["point"] <= pred["upper"]).all()
    assert (pred["lower"] >= 0).all()
    assert (pred.loc[~test["is_open"]] == 0).all().all()


def test_forecaster_beats_baseline(
    fitted: tuple[DemandForecaster, pd.DataFrame],
) -> None:
    model, test = fitted
    open_rows = test[test["is_open"]]
    y = open_rows["units_sold"].to_numpy(dtype=float)
    model_err = wape(y, model.predict(open_rows)["point"].to_numpy())
    base_err = wape(y, seasonal_naive(open_rows).to_numpy())
    assert model_err < base_err


def test_forecaster_guards() -> None:
    with pytest.raises(ValueError, match="lower_q"):
        DemandForecaster(lower_q=0.6)
    with pytest.raises(RuntimeError, match="not fitted"):
        DemandForecaster().predict(pd.DataFrame())
    empty = pd.DataFrame({"is_open": pd.Series([], dtype=bool)})
    with pytest.raises(ValueError, match="no trading-day"):
        DemandForecaster().fit(empty)


def test_safety_stock_bridge() -> None:
    assert safety_stock_units(40.2, 47.1) == 7
    assert safety_stock_units(40.0, 39.0) == 0


def test_backtest_runs_and_reports(sales: pd.DataFrame) -> None:
    results, by_sku = run_backtest(sales, [date(2025, 6, 1)], test_days=28)
    assert len(results) == 1
    assert results[0].wape_model < results[0].wape_baseline
    report = render_report(results, by_sku, horizon=2)
    assert "weighted mean" in report
    assert "do not predict real-world accuracy" in report


def test_backtest_cli_writes_report(
    sales: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from freshcast.models import backtest

    data = tmp_path / "sales.csv"
    sales.to_csv(data, index=False)
    out = tmp_path / "r.md"
    monkeypatch.setattr(sys, "argv", ["x", "--data", str(data), "--out", str(out)])
    backtest.main()
    assert "Backtest results" in out.read_text(encoding="utf-8")
