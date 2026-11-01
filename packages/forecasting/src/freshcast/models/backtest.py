"""Rolling-origin backtest comparing LightGBM with the seasonal-naive baseline.

For each origin the model is trained only on days before the origin and
evaluated on the following ``test_days`` days. Features for test rows use
actuals up to ``t - horizon``, exactly what is known when a forecast is issued.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from freshcast.features.builder import build_features
from freshcast.models.baseline import seasonal_naive
from freshcast.models.lgbm import DemandForecaster
from freshcast.models.metrics import bias, interval_coverage, mae, wape


@dataclass(frozen=True, slots=True)
class FoldResult:
    """Metrics for one backtest fold."""

    origin: date
    wape_baseline: float
    wape_model: float
    mae_baseline: float
    mae_model: float
    bias_baseline: float
    bias_model: float
    coverage: float
    n_rows: int


def run_backtest(
    sales: pd.DataFrame,
    origins: list[date],
    horizon: int = 2,
    test_days: int = 28,
    calibration_days: int = 28,
) -> tuple[list[FoldResult], pd.DataFrame]:
    """Run all folds; return fold metrics and per-SKU model WAPE."""
    feats = build_features(sales, horizon)
    results: list[FoldResult] = []
    sku_rows: list[pd.DataFrame] = []
    for origin in origins:
        start = pd.Timestamp(origin)
        end = start + pd.Timedelta(days=test_days)
        train = feats[feats["business_date"] < start - pd.Timedelta(days=horizon)]
        test = feats[
            (feats["business_date"] >= start)
            & (feats["business_date"] < end)
            & feats["is_open"]
        ]
        model = DemandForecaster(calibration_days=calibration_days).fit(train)
        pred = model.predict(test)
        base = seasonal_naive(test)
        y = test["units_sold"].to_numpy(dtype=np.float64)
        p = pred["point"].to_numpy(dtype=np.float64)
        b = base.to_numpy(dtype=np.float64)
        results.append(
            FoldResult(
                origin=origin,
                wape_baseline=wape(y, b),
                wape_model=wape(y, p),
                mae_baseline=mae(y, b),
                mae_model=mae(y, p),
                bias_baseline=bias(y, b),
                bias_model=bias(y, p),
                coverage=interval_coverage(
                    y,
                    pred["lower"].to_numpy(dtype=np.float64),
                    pred["upper"].to_numpy(dtype=np.float64),
                ),
                n_rows=len(test),
            )
        )
        sku_rows.append(
            pd.DataFrame({"sku": test["sku"], "abs_err": np.abs(y - p), "actual": y})
        )
    by_sku = pd.concat(sku_rows).groupby("sku").sum()
    by_sku["wape_model"] = by_sku["abs_err"] / by_sku["actual"]
    return results, by_sku[["wape_model"]].sort_values("wape_model")


def _weighted(results: list[FoldResult], attr: str) -> float:
    """Row-weighted mean of a fold metric."""
    total = sum(r.n_rows for r in results)
    return float(sum(getattr(r, attr) * r.n_rows for r in results) / total)


def render_report(results: list[FoldResult], by_sku: pd.DataFrame, horizon: int) -> str:
    """Render a Markdown report (synthetic data: not evidence of real accuracy)."""
    header = (
        "| Origin | WAPE baseline | WAPE LightGBM | MAE baseline | MAE LightGBM "
        "| Bias LightGBM | 80% interval coverage |"
    )
    lines = [
        "# Backtest results (synthetic data)",
        "",
        f"Forecast issued {horizon} days ahead; trading days only; rolling origins.",
        "",
        header,
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.origin} | {r.wape_baseline:.1%} | {r.wape_model:.1%} "
            f"| {r.mae_baseline:.2f} | {r.mae_model:.2f} "
            f"| {r.bias_model:+.1%} | {r.coverage:.1%} |"
        )
    lines += [
        f"| **weighted mean** | {_weighted(results, 'wape_baseline'):.1%} "
        f"| {_weighted(results, 'wape_model'):.1%} "
        f"| {_weighted(results, 'mae_baseline'):.2f} "
        f"| {_weighted(results, 'mae_model'):.2f} "
        f"| {_weighted(results, 'bias_model'):+.1%} "
        f"| {_weighted(results, 'coverage'):.1%} |",
        "",
        "## LightGBM WAPE by SKU",
        "",
        "| SKU | WAPE |",
        "|---|---|",
        *[f"| {sku} | {row.wape_model:.1%} |" for sku, row in by_sku.iterrows()],
        "",
        "Data is simulated with Gaussian noise, so these numbers show the pipeline "
        "works and is leakage-safe; they do not predict real-world accuracy.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Run the rolling-origin backtest")
    parser.add_argument("--data", type=Path, default=Path("data/synthetic/sales.csv"))
    parser.add_argument("--out", type=Path, default=Path("docs/ml/backtest-results.md"))
    parser.add_argument("--horizon", type=int, default=2)
    args = parser.parse_args()
    sales = pd.read_csv(args.data, parse_dates=["business_date"])
    last = sales["business_date"].max().date()
    origins = [last - timedelta(days=28 * k) + timedelta(days=1) for k in (4, 3, 2, 1)]
    results, by_sku = run_backtest(sales, origins, args.horizon)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(results, by_sku, args.horizon), encoding="utf-8")


if __name__ == "__main__":
    main()
