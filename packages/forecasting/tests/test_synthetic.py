"""Tests for the synthetic data generator."""

import csv
from datetime import date
from pathlib import Path

import pytest

from freshcast.data.synthetic import PRODUCTS, STORES, generate_sales, write_dataset
from freshcast.domain.entities import Currency

START = date(2026, 1, 1)


def test_deterministic_for_same_seed() -> None:
    a = list(generate_sales(START, 14, seed=1))
    b = list(generate_sales(START, 14, seed=1))
    c = list(generate_sales(START, 14, seed=2))
    assert a == b
    assert a != c


def test_row_count_is_stores_times_products_times_days() -> None:
    rows = list(generate_sales(START, 10))
    assert len(rows) == len(STORES) * len(PRODUCTS) * 10


def test_closed_days_have_no_sales_or_promos() -> None:
    closed = [r for r in generate_sales(START, 60) if not r.is_open]
    assert closed
    assert all(r.units_sold == 0 and not r.is_promo for r in closed)


def test_no_negative_values_and_currency_matches_store() -> None:
    currency = {s.store_id: s.currency for s in STORES}
    for r in generate_sales(START, 30):
        assert r.units_sold >= 0
        assert r.unit_price > 0
        assert r.currency is currency[r.store_id]


def test_swiss_prices_higher_than_german_for_same_sku() -> None:
    rows = [
        r
        for r in generate_sales(date(2026, 3, 2), 1)  # Monday, open
        if r.sku == "MILK-1L" and not r.is_promo
    ]
    ch = [r.unit_price for r in rows if r.currency is Currency.CHF]
    de = [r.unit_price for r in rows if r.currency is Currency.EUR]
    assert min(ch) > max(de)


def test_strawberries_peak_in_summer() -> None:
    def total(month_start: date) -> int:
        return sum(
            r.units_sold
            for r in generate_sales(month_start, 28)
            if r.sku == "STRAWBERRY-500G"
        )

    assert total(date(2026, 6, 1)) > 2 * total(date(2026, 12, 1))


def test_invalid_days_rejected() -> None:
    with pytest.raises(ValueError, match="days"):
        list(generate_sales(START, 0))


def test_write_dataset_creates_csv_files(tmp_path: Path) -> None:
    write_dataset(tmp_path, START, 3)
    with (tmp_path / "sales.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(STORES) * len(PRODUCTS) * 3
    assert (tmp_path / "stores.csv").exists()
    assert (tmp_path / "products.csv").exists()
