"""Newsvendor (critical-ratio) order target.

Why
---
A fixed safety stock treats a unit too many and a unit too few as equally bad.
For fresh goods they are not: an unsold unit costs its purchase price (waste),
a missed sale costs the margin. The classic newsvendor result says to cover
demand up to the *critical ratio*::

    CR = underage / (underage + overage)
       = unit_margin / (unit_margin + unit_cost * overage_factor)

and order up to the CR-quantile of demand. With a 40 % margin and 60 % cost the
ratio is 0.4 (below 0.5), so the best target is slightly *below* the expected
demand: for these economics, over-ordering costs more than under-ordering.

Assumptions (stated, not hidden)
--------------------------------
* Demand over the covered days is approximately normal, with the standard
  deviation taken from the (calibrated) 80 % interval of the forecaster.
* Daily errors are independent, so variances add over the covered days.
* ``overage_factor`` is the share of the unit cost that is really lost when a
  unit is left over (1.0 = it cannot be carried to the next day).
"""

from __future__ import annotations

import math
from statistics import NormalDist

# z-value of the 90 % quantile: an 80 % central interval spans +/- 1.2816 sigma.
Z_90 = NormalDist().inv_cdf(0.9)


def critical_ratio(
    unit_cost: float, unit_margin: float, overage_factor: float = 1.0
) -> float:
    """Return the critical ratio in (0, 1)."""
    if unit_cost < 0 or unit_margin < 0 or overage_factor < 0:
        raise ValueError("costs and overage_factor cannot be negative")
    overage = unit_cost * overage_factor
    if unit_margin + overage <= 0:
        raise ValueError("underage and overage cannot both be zero")
    # Clamp away from 0 and 1 so the normal quantile stays finite.
    return min(0.999, max(0.001, unit_margin / (unit_margin + overage)))


def sigma_from_interval(lower: float, upper: float) -> float:
    """Return the standard deviation implied by an 80 % interval (normal)."""
    if upper < lower:
        raise ValueError("upper must not be below lower")
    return (upper - lower) / (2 * Z_90)


def newsvendor_target(
    point: list[float], lower: list[float], upper: list[float], ratio: float
) -> float:
    """Units to cover over the given days: mean + z(CR) * sigma, never below 0."""
    if not (len(point) == len(lower) == len(upper)):
        raise ValueError("forecast lists must have equal length")
    if not 0 < ratio < 1:
        raise ValueError("ratio must be in (0, 1)")
    mean = sum(point)
    variance = sum(
        sigma_from_interval(lo, hi) ** 2 for lo, hi in zip(lower, upper, strict=True)
    )
    z = NormalDist().inv_cdf(ratio)
    return max(0.0, mean + z * math.sqrt(variance))
