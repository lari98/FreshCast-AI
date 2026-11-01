"""Deterministic synthetic sales generator for DE/AT/CH supermarkets.

Everything is invented: stores, products, prices and demand. Given the same
seed the output is byte-identical, which keeps tests and demos reproducible.
Demand = base * store size * weekday * season * promo uplift + noise.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections.abc import Iterator
from dataclasses import asdict, fields
from datetime import date, timedelta
from pathlib import Path

from freshcast.data.calendar import is_holiday, is_store_open
from freshcast.domain.entities import (
    Country,
    Currency,
    Product,
    SalesRecord,
    Store,
)

STORES: tuple[Store, ...] = (
    Store("DE-MUC-001", Country.DE, "Munich", Currency.EUR, 1.3),
    Store("DE-BER-001", Country.DE, "Berlin", Currency.EUR, 1.1),
    Store("DE-ING-001", Country.DE, "Ingolstadt", Currency.EUR, 0.8),
    Store("AT-VIE-001", Country.AT, "Vienna", Currency.EUR, 1.2),
    Store("AT-GRZ-001", Country.AT, "Graz", Currency.EUR, 0.9),
    Store("CH-ZRH-001", Country.CH, "Zurich", Currency.CHF, 1.2),
    Store("CH-PFA-001", Country.CH, "Pfaeffikon SZ", Currency.CHF, 0.7),
)

PRODUCTS: tuple[Product, ...] = (
    Product(
        "STRAWBERRY-500G",
        "Erdbeeren 500 g",
        "Strawberries 500 g",
        "fruit",
        3.49,
        4,
        12,
        40,
    ),
    Product("MILK-1L", "Frischmilch 1 l", "Fresh milk 1 l", "dairy", 1.29, 7, 6, 90),
    Product(
        "BREAD-WHEAT-750G",
        "Weizenbrot 750 g",
        "Wheat bread 750 g",
        "bakery",
        2.79,
        2,
        10,
        60,
    ),
    Product("YOGURT-500G", "Joghurt 500 g", "Yoghurt 500 g", "dairy", 1.49, 14, 8, 55),
    Product(
        "SALAD-MIXED-200G",
        "Blattsalat 200 g",
        "Mixed salad 200 g",
        "vegetable",
        1.99,
        3,
        10,
        35,
    ),
    Product(
        "CHICKEN-BREAST-500G",
        "Haehnchenbrust 500 g",
        "Chicken breast 500 g",
        "meat",
        6.99,
        4,
        6,
        25,
    ),
    Product(
        "TOMATO-500G", "Tomaten 500 g", "Tomatoes 500 g", "vegetable", 2.29, 6, 10, 45
    ),
    Product(
        "SALMON-FILLET-250G",
        "Lachsfilet 250 g",
        "Salmon fillet 250 g",
        "fish",
        5.99,
        3,
        6,
        18,
    ),
)

# Illustrative price level in Switzerland relative to Germany/Austria.
CHF_PRICE_FACTOR = 1.15
WEEKDAY_FACTOR = (0.95, 0.9, 0.95, 1.0, 1.2, 1.5, 0.0)  # Mon..Sun
PROMO_PROBABILITY = 0.08
PROMO_DISCOUNT = 0.20
PROMO_UPLIFT = 1.35


def _season_factor(product: Product, day: date) -> float:
    """Return a smooth annual seasonality multiplier for the product."""
    phase = 2 * math.pi * (day.timetuple().tm_yday - 172) / 365  # peak ~21 Jun
    if product.sku == "STRAWBERRY-500G":
        return 1.0 + 0.8 * math.cos(phase)
    if product.category == "vegetable":
        return 1.0 + 0.25 * math.cos(phase)
    return 1.0 + 0.05 * math.cos(phase)


def generate_sales(start: date, days: int, seed: int = 42) -> Iterator[SalesRecord]:
    """Yield one record per store, product and day, in stable order."""
    if days <= 0:
        raise ValueError("days must be positive")
    # Not used for security; a seeded PRNG is required for reproducible data.
    rng = random.Random(seed)  # noqa: S311  # nosec B311
    for offset in range(days):
        day = start + timedelta(days=offset)
        for store in STORES:
            open_today = is_store_open(store.country, day)
            holiday = is_holiday(store.country, day)
            for product in PRODUCTS:
                promo = open_today and rng.random() < PROMO_PROBABILITY
                price = product.base_price_eur
                if store.currency is Currency.CHF:
                    price *= CHF_PRICE_FACTOR
                if promo:
                    price *= 1 - PROMO_DISCOUNT
                units = 0
                if open_today:
                    mean = (
                        product.base_daily_demand
                        * store.size_factor
                        * WEEKDAY_FACTOR[day.weekday()]
                        * _season_factor(product, day)
                        * (PROMO_UPLIFT if promo else 1.0)
                    )
                    # Gaussian approximation of Poisson noise (sd = sqrt(mean)).
                    units = max(0, round(rng.gauss(mean, math.sqrt(max(mean, 1.0)))))
                yield SalesRecord(
                    business_date=day,
                    store_id=store.store_id,
                    sku=product.sku,
                    units_sold=units,
                    unit_price=round(price, 2),
                    currency=store.currency,
                    is_open=open_today,
                    is_holiday=holiday,
                    is_promo=promo,
                )


def _write_csv(path: Path, header: list[str], rows: Iterator[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_dataset(out_dir: Path, start: date, days: int, seed: int = 42) -> None:
    """Write stores.csv, products.csv and sales.csv into out_dir."""
    store_fields = [f.name for f in fields(Store)]
    product_fields = [f.name for f in fields(Product)]
    sales_fields = [f.name for f in fields(SalesRecord)]
    _write_csv(
        out_dir / "stores.csv",
        store_fields,
        ([asdict(s)[k] for k in store_fields] for s in STORES),
    )
    _write_csv(
        out_dir / "products.csv",
        product_fields,
        ([asdict(p)[k] for k in product_fields] for p in PRODUCTS),
    )
    _write_csv(
        out_dir / "sales.csv",
        sales_fields,
        (
            [asdict(r)[k] for k in sales_fields]
            for r in generate_sales(start, days, seed)
        ),
    )


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Generate synthetic DACH data")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args()
    write_dataset(args.out, args.start, args.days, args.seed)


if __name__ == "__main__":
    main()
