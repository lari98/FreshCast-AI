"""Forecast accuracy metrics (all on trading days, weighted by volume)."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.floating[Any]]


def wape(actual: Array, forecast: Array) -> float:
    """Weighted absolute percentage error: sum|e| / sum(actual)."""
    total = float(np.sum(actual))
    if total == 0:
        raise ValueError("WAPE undefined when total actual demand is zero")
    return float(np.sum(np.abs(actual - forecast)) / total)


def mae(actual: Array, forecast: Array) -> float:
    """Mean absolute error in units."""
    return float(np.mean(np.abs(actual - forecast)))


def bias(actual: Array, forecast: Array) -> float:
    """Relative bias: (sum forecast - sum actual) / sum actual; >0 over-forecasts."""
    total = float(np.sum(actual))
    if total == 0:
        raise ValueError("bias undefined when total actual demand is zero")
    return float((np.sum(forecast) - total) / total)


def interval_coverage(actual: Array, lower: Array, upper: Array) -> float:
    """Share of actuals inside [lower, upper]."""
    return float(np.mean((actual >= lower) & (actual <= upper)))
