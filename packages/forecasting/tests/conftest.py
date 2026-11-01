"""Shared fixtures."""

from dataclasses import asdict
from datetime import date

import pandas as pd
import pytest

from freshcast.data.synthetic import generate_sales


@pytest.fixture(scope="session")
def sales() -> pd.DataFrame:
    """Seven months of synthetic sales (enough for lag_28 and a test window)."""
    rows = [asdict(r) for r in generate_sales(date(2025, 1, 1), 200, seed=7)]
    return pd.DataFrame(rows)
