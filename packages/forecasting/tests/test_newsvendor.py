"""Critical-ratio target: monotonicity, clamping and validation."""

import pytest

from freshcast.replenishment.newsvendor import (
    Z_90,
    critical_ratio,
    newsvendor_target,
    sigma_from_interval,
)


def test_critical_ratio_with_forty_percent_margin_is_below_half() -> None:
    assert critical_ratio(0.6, 0.4) == pytest.approx(0.4)


def test_lower_overage_factor_raises_the_ratio() -> None:
    assert critical_ratio(0.6, 0.4, 0.1) > critical_ratio(0.6, 0.4, 1.0)


def test_ratio_is_clamped_and_validated() -> None:
    assert critical_ratio(0.0, 1.0) == 0.999
    with pytest.raises(ValueError, match="cannot be negative"):
        critical_ratio(-1, 1)
    with pytest.raises(ValueError, match="both be zero"):
        critical_ratio(0, 0)


def test_sigma_from_interval() -> None:
    assert sigma_from_interval(10, 10) == 0
    assert sigma_from_interval(8, 12) == pytest.approx(4 / (2 * Z_90))
    with pytest.raises(ValueError, match="upper"):
        sigma_from_interval(5, 4)


def test_target_equals_mean_at_half_and_grows_with_ratio() -> None:
    point, lower, upper = [10.0, 20.0], [6.0, 14.0], [14.0, 26.0]
    assert newsvendor_target(point, lower, upper, 0.5) == pytest.approx(30.0)
    assert newsvendor_target(point, lower, upper, 0.9) > 30.0
    assert newsvendor_target(point, lower, upper, 0.2) < 30.0


def test_target_never_negative_and_inputs_validated() -> None:
    assert newsvendor_target([0.0], [0.0], [50.0], 0.001) == 0.0
    with pytest.raises(ValueError, match="equal length"):
        newsvendor_target([1.0], [1.0, 2.0], [1.0], 0.5)
    with pytest.raises(ValueError, match="ratio"):
        newsvendor_target([1.0], [1.0], [1.0], 1.0)
