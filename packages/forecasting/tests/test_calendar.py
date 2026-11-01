"""Tests for the DACH holiday calendar."""

from datetime import date

from freshcast.data.calendar import easter_sunday, is_holiday, is_store_open
from freshcast.domain.entities import Country


def test_easter_known_dates() -> None:
    assert easter_sunday(2025) == date(2025, 4, 20)
    assert easter_sunday(2026) == date(2026, 4, 5)


def test_country_specific_holidays() -> None:
    assert is_holiday(Country.DE, date(2026, 10, 3))
    assert not is_holiday(Country.AT, date(2026, 10, 3))
    assert is_holiday(Country.AT, date(2026, 10, 26))
    assert is_holiday(Country.CH, date(2026, 8, 1))


def test_movable_holidays() -> None:
    assert is_holiday(Country.DE, date(2026, 4, 3))  # Good Friday
    assert is_holiday(Country.CH, date(2026, 5, 14))  # Ascension


def test_stores_closed_sundays_and_holidays() -> None:
    assert not is_store_open(Country.DE, date(2026, 11, 1))  # Sunday
    assert not is_store_open(Country.DE, date(2026, 12, 25))
    assert is_store_open(Country.DE, date(2026, 11, 2))  # Monday
