"""Simplified public-holiday and opening-day calendar for DE/AT/CH.

Only nationwide holidays are modelled. Regional holidays (e.g. Bavarian
Corpus Christi, Swiss cantonal days) are deliberately omitted, so this is a
demo calendar and must be replaced by an official source for production use.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache

from freshcast.domain.entities import Country


def easter_sunday(year: int) -> date:
    """Return Easter Sunday (Gregorian computus, Anonymous algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


@cache
def holidays(country: Country, year: int) -> frozenset[date]:
    """Return nationwide public holidays for a country and year."""
    easter = easter_sunday(year)
    movable = {
        easter - timedelta(days=2),  # Good Friday
        easter + timedelta(days=1),  # Easter Monday
        easter + timedelta(days=39),  # Ascension
        easter + timedelta(days=50),  # Whit Monday
    }
    fixed = {date(year, 1, 1), date(year, 12, 25), date(year, 12, 26)}
    if country is Country.DE:
        fixed |= {date(year, 5, 1), date(year, 10, 3)}
    elif country is Country.AT:
        fixed |= {
            date(year, 1, 6),
            date(year, 5, 1),
            date(year, 8, 15),
            date(year, 10, 26),
            date(year, 11, 1),
            date(year, 12, 8),
        }
    else:  # Switzerland
        fixed |= {date(year, 8, 1)}
    return frozenset(movable | fixed)


def is_holiday(country: Country, day: date) -> bool:
    """Return True if the day is a nationwide public holiday."""
    return day in holidays(country, day.year)


def is_store_open(country: Country, day: date) -> bool:
    """Return True if a typical grocery store trades (closed Sundays/holidays)."""
    return day.weekday() != 6 and not is_holiday(country, day)
