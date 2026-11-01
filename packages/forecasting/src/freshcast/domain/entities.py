"""Core domain entities shared by data generation, features and the API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Country(StrEnum):
    """Supported DACH markets (ISO 3166-1 alpha-2)."""

    DE = "DE"
    AT = "AT"
    CH = "CH"


class Currency(StrEnum):
    """Price currencies (ISO 4217)."""

    EUR = "EUR"
    CHF = "CHF"


@dataclass(frozen=True, slots=True)
class Store:
    """A retail location. Synthetic only: no real company or person."""

    store_id: str
    country: Country
    city: str
    currency: Currency
    size_factor: float  # relative footfall; 1.0 = average store


@dataclass(frozen=True, slots=True)
class Product:
    """A perishable SKU with its commercial shelf-life assumption."""

    sku: str
    name_de: str
    name_en: str
    category: str
    base_price_eur: float
    shelf_life_days: int
    pack_size: int  # supplier order multiple
    base_daily_demand: float  # units per average store on an average open day


@dataclass(frozen=True, slots=True)
class SalesRecord:
    """One store/SKU/day observation."""

    business_date: date
    store_id: str
    sku: str
    units_sold: int
    unit_price: float
    currency: Currency
    is_open: bool
    is_holiday: bool
    is_promo: bool
