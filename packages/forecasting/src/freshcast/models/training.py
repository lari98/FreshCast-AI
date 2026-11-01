"""Training entry point (SageMaker script mode compatible).

Reads ``sales.csv`` from the training channel, evaluates on a hold-out window,
refits on all data and writes ``model.joblib`` plus ``metrics.json`` containing
version and data fingerprints, so any published forecast can be traced back to
the exact model, data and code that produced it.

Security note: ``model.joblib`` is a pickle. Only load artifacts produced by
your own pipeline from buckets you control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

import freshcast
from freshcast.features.builder import build_features
from freshcast.models.baseline import seasonal_naive
from freshcast.models.lgbm import DemandForecaster
from freshcast.models.metrics import bias, interval_coverage, wape


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(
    data_file: Path, model_dir: Path, horizon: int = 2, holdout_days: int = 28
) -> dict[str, Any]:
    """Train, evaluate on a hold-out, refit on everything and save artifacts."""
    sales = pd.read_csv(data_file, parse_dates=["business_date"])
    feats = build_features(sales, horizon)
    start = feats["business_date"].max() - pd.Timedelta(days=holdout_days - 1)
    fit_part = feats[feats["business_date"] < start - pd.Timedelta(days=horizon)]
    test = feats[(feats["business_date"] >= start) & feats["is_open"]]

    pred = DemandForecaster(calibration_days=28).fit(fit_part).predict(test)
    y = test["units_sold"].to_numpy(dtype=np.float64)
    base = seasonal_naive(test).to_numpy(dtype=np.float64)
    model_wape = wape(y, pred["point"].to_numpy(dtype=np.float64))
    base_wape = wape(y, base)

    final = DemandForecaster(calibration_days=28).fit(
        feats
    )  # production model sees all history
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, model_dir / "model.joblib")
    metrics: dict[str, Any] = {
        "wape_model": model_wape,
        "wape_baseline": base_wape,
        "bias_model": bias(y, pred["point"].to_numpy(dtype=np.float64)),
        "interval_coverage": interval_coverage(
            y,
            pred["lower"].to_numpy(dtype=np.float64),
            pred["upper"].to_numpy(dtype=np.float64),
        ),
        # Promotion gate: only models that beat the benchmark may be approved.
        "beats_baseline": model_wape < base_wape,
        "horizon_days": horizon,
        "holdout_days": holdout_days,
        "training_rows": int(len(feats)),
        "code_version": freshcast.__version__,
        "data_sha256": _sha256(data_file),
    }
    (model_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metrics


def main() -> None:
    """Command-line / SageMaker entry point."""
    parser = argparse.ArgumentParser(description="Train the FreshCast forecaster")
    parser.add_argument(
        "--train",
        type=Path,
        default=Path(os.environ.get("SM_CHANNEL_TRAINING", "data/synthetic")),
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(os.environ.get("SM_MODEL_DIR", "build/model")),
    )
    parser.add_argument("--horizon", type=int, default=2)
    args = parser.parse_args()
    metrics = train(args.train / "sales.csv", args.model_dir, args.horizon)
    print(json.dumps(metrics, indent=2, sort_keys=True))  # noqa: T201 - job log


if __name__ == "__main__":
    main()
