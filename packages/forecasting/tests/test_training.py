"""Training pipeline: artifacts, traceability and the promotion gate."""

import hashlib
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

from freshcast.models import training
from freshcast.models.lgbm import DemandForecaster


@pytest.fixture
def data_file(sales: pd.DataFrame, tmp_path: Path) -> Path:
    path = tmp_path / "sales.csv"
    sales.to_csv(path, index=False)
    return path


def test_train_writes_traceable_artifacts(data_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "model"
    metrics = training.train(data_file, out)
    assert metrics["beats_baseline"] is True
    assert metrics["wape_model"] < metrics["wape_baseline"]
    assert metrics["data_sha256"] == hashlib.sha256(data_file.read_bytes()).hexdigest()
    saved = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert saved["code_version"] == metrics["code_version"]
    assert isinstance(joblib.load(out / "model.joblib"), DemandForecaster)


def test_cli_uses_sagemaker_environment(
    data_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "sm-model"
    monkeypatch.setenv("SM_CHANNEL_TRAINING", str(data_file.parent))
    monkeypatch.setenv("SM_MODEL_DIR", str(out))
    monkeypatch.setattr(sys, "argv", ["train"])
    training.main()
    assert (out / "model.joblib").exists()
