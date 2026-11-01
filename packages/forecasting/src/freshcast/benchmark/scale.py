"""Scale benchmark: pipeline cost as the number of store/SKU series grows.

A supermarket chain forecasts tens of thousands of store/SKU series every day.
This module generates synthetic series (vectorised, so generation is not the
bottleneck), then times the three operations that matter:

* feature building (daily, for all series),
* prediction (daily, for all series),
* training (weekly or less often; one *global* model for all series).

Measurements are for the machine that runs them (reported in the output) and
for synthetic data. They show how cost grows with the number of series; they
are not a promise about any production environment.
"""

from __future__ import annotations

import argparse
import platform
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from freshcast.features.builder import build_features
from freshcast.models.lgbm import DemandForecaster

SKUS_PER_STORE = 200


def generate_series(n_series: int, days: int = 90, seed: int = 7) -> pd.DataFrame:
    """Create ``n_series`` synthetic store/SKU daily series (Sundays closed)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    n_stores = max(1, -(-n_series // SKUS_PER_STORE))
    idx = np.arange(n_series)
    base = rng.lognormal(mean=2.2, sigma=0.8, size=n_series)
    dow_effect = np.array([1.0, 0.95, 0.95, 1.0, 1.15, 1.45, 0.0])
    weekday = dates.day_of_week.to_numpy()
    mean = base[:, None] * dow_effect[weekday][None, :]
    promo = rng.random((n_series, days)) < 0.05
    mean = mean * np.where(promo, 1.6, 1.0)
    units = rng.poisson(mean).astype(np.int32)
    return pd.DataFrame(
        {
            "store_id": np.repeat([f"S{i // SKUS_PER_STORE:04d}" for i in idx], days),
            "sku": np.repeat([f"K{i % SKUS_PER_STORE:04d}" for i in idx], days),
            "business_date": np.tile(dates, n_series),
            "units_sold": units.ravel(),
            "is_open": np.tile(weekday != 6, n_series),
            "is_holiday": False,
            "is_promo": promo.ravel(),
            "unit_price": np.float32(2.0),
        }
    ).assign(n_stores=n_stores)


@dataclass(frozen=True, slots=True)
class ScaleResult:
    """Timings in seconds for one problem size."""

    n_series: int
    rows: int
    features_s: float
    train_s: float | None
    predict_s: float


def measure(
    n_series: int,
    days: int = 90,
    train: bool = True,
    model: DemandForecaster | None = None,
    n_jobs: int = 2,
) -> tuple[ScaleResult, DemandForecaster | None]:
    """Time features, optional training, and prediction for one size."""
    sales = generate_series(n_series, days).drop(columns="n_stores")
    t0 = time.perf_counter()
    feats = build_features(sales, horizon=2)
    t_feat = time.perf_counter() - t0

    t_train: float | None = None
    if train:
        t0 = time.perf_counter()
        model = DemandForecaster(n_jobs=n_jobs).fit(feats)
        t_train = time.perf_counter() - t0
    if model is None:
        raise ValueError("a fitted model is required when train=False")

    last_day = feats["business_date"].max()
    today = feats[(feats["business_date"] == last_day) & feats["is_open"]]
    if today.empty:  # last day closed: use the previous day
        today = feats[feats["business_date"] == last_day - pd.Timedelta(days=1)]
    # Predict a full day's worth of rows for every series.
    t0 = time.perf_counter()
    model.predict(today)
    t_pred = time.perf_counter() - t0
    return ScaleResult(n_series, len(sales), t_feat, t_train, t_pred), model


def render(results: list[ScaleResult], note: str) -> str:
    """Render the benchmark as Markdown."""
    lines = [
        "# Scale benchmark (synthetic data)",
        "",
        f"Machine: {platform.processor() or platform.machine()}, "
        f"Python {platform.python_version()}. {note}",
        "",
        "| Series (store x SKU) | History rows | Feature build | Training "
        "| Daily prediction |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        train = f"{r.train_s:.1f} s" if r.train_s is not None else "reused model"
        lines.append(
            f"| {r.n_series:,} | {r.rows:,} | {r.features_s:.1f} s | {train} "
            f"| {r.predict_s:.2f} s |"
        )
    lines += [
        "",
        "Reading: one global model serves all series, so training cost grows "
        "roughly linearly with rows and is paid weekly or less, while the daily "
        "path (features + prediction) is what runs every day. These are "
        "single-machine, synthetic-data numbers, not a production guarantee.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Run the scale benchmark")
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 5000, 20000])
    parser.add_argument("--predict-size", type=int, default=50000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--out", type=Path, default=Path("docs/ml/scale-benchmark.md"))
    args = parser.parse_args()
    results: list[ScaleResult] = []
    model: DemandForecaster | None = None
    for n in args.sizes:
        result, model = measure(n, args.days)
        results.append(result)
        print(result, flush=True)  # noqa: T201
    big, _ = measure(args.predict_size, args.days, train=False, model=model)
    results.append(big)
    print(big, flush=True)  # noqa: T201
    note = (
        f"Last row ({args.predict_size:,} series) reuses the model trained on "
        f"{args.sizes[-1]:,} series, to time the daily path at that size."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(results, note), encoding="utf-8")


if __name__ == "__main__":
    main()
