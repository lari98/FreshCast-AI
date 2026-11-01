"""Read and validate user-supplied sales and stock CSV files.

Real exports are messy, so this module is strict about what it accepts and
explicit about what it changes. Every repair (dropped rows, filled days,
rounded quantities) is reported in the :class:`QualityReport` instead of being
done silently. Files are processed in memory only; nothing is stored or logged.

DACH specifics handled here: ``;`` as separator, decimal comma, ``dd.mm.yyyy``
dates, German column names, UTF-8 with BOM (typical for Excel exports).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from freshcast.data.calendar import is_holiday, is_store_open
from freshcast.domain.entities import Country

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 500_000
MAX_SERIES = 300
MIN_HISTORY_DAYS = 60
STALE_DAYS = 14

# German and common alternative column names -> canonical names.
ALIASES: dict[str, str] = {
    "filiale": "store_id",
    "markt": "store_id",
    "store": "store_id",
    "artikel": "sku",
    "artikelnummer": "sku",
    "article": "sku",
    "datum": "business_date",
    "date": "business_date",
    "menge": "units_sold",
    "absatz": "units_sold",
    "verkauf": "units_sold",
    "units": "units_sold",
    "artikelname": "product_name",
    "bezeichnung": "product_name",
    "preis": "unit_price",
    "price": "unit_price",
    "haltbarkeit_tage": "shelf_life_days",
    "gebindegroesse": "pack_size",
    "bestand": "quantity",
    "mhd": "use_by_date",
    "charge": "lot_id",
    "warengruppe": "category",
    "kategorie": "category",
    "handelskette": "chain",
    "kette": "chain",
    "retailer": "chain",
    "banner": "chain",
}
REQUIRED_SALES = ("store_id", "sku", "business_date", "units_sold")
REQUIRED_STOCK = ("store_id", "sku", "quantity", "use_by_date")


class IngestError(ValueError):
    """The upload cannot be used; ``problems`` explains what to fix."""

    def __init__(self, problems: list[str]) -> None:
        """Keep every problem so the user can fix them in one go."""
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(slots=True)
class QualityReport:
    """What was found and what was changed while reading the upload."""

    rows_in: int = 0
    rows_used: int = 0
    series_used: int = 0
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    date_from: str = ""
    date_to: str = ""
    calibrated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form for the API and dashboard."""
        return {
            "rows_in": self.rows_in,
            "rows_used": self.rows_used,
            "series_used": self.series_used,
            "skipped": self.skipped,
            "warnings": self.warnings,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "calibrated": self.calibrated,
        }


def read_csv_bytes(data: bytes, name: str = "file") -> pd.DataFrame:
    """Parse CSV bytes into a string-typed frame with canonical column names."""
    if len(data) > MAX_BYTES:
        raise IngestError([f"{name}: file larger than {MAX_BYTES // 2**20} MB"])
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")  # common for older German exports
    head = text.splitlines()[0] if text.strip() else ""
    sep = max((";", ",", "\t"), key=head.count)
    if head.count(sep) == 0:
        raise IngestError([f"{name}: could not find a header row with columns"])
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [ALIASES.get(c.strip().lower(), c.strip().lower()) for c in df.columns]
    df.attrs["decimal_comma"] = sep == ";"
    return df


def _numeric(series: pd.Series, decimal_comma: bool) -> pd.Series:
    text = series.str.strip()
    if decimal_comma:
        text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y")


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates with the one format that fits most rows (no day/month guessing)."""
    text = series.str.strip().str.slice(0, 10)
    best = max(
        (pd.to_datetime(text, format=f, errors="coerce") for f in DATE_FORMATS),
        key=lambda parsed: int(parsed.notna().sum()),
    )
    return best


def _country(store_id: str) -> Country:
    prefix = store_id[:2].upper()
    return Country(prefix) if prefix in Country.__members__ else Country.DE


def clean_sales(
    raw: pd.DataFrame, as_of: date | None = None
) -> tuple[pd.DataFrame, QualityReport, date]:
    """Validate and repair sales rows; return the daily panel, report, as-of date."""
    report = QualityReport(rows_in=len(raw))
    missing = [c for c in REQUIRED_SALES if c not in raw.columns]
    if missing:
        raise IngestError([f"missing required column(s): {', '.join(missing)}"])
    if len(raw) > MAX_ROWS:
        raise IngestError([f"more than {MAX_ROWS:,} rows; split the file by store"])
    comma = bool(raw.attrs.get("decimal_comma", False))

    df = pd.DataFrame(
        {
            "store_id": raw["store_id"].str.strip(),
            "sku": raw["sku"].str.strip(),
            "business_date": _parse_dates(raw["business_date"]),
            "units_sold": _numeric(raw["units_sold"], comma),
        }
    )
    for col, default in (
        ("product_name", None),
        ("category", None),
        ("chain", None),
        ("is_open", None),
    ):
        if col in raw.columns:
            df[col] = raw[col].str.strip()
        elif default is not None:
            df[col] = default
    for col in ("unit_price", "shelf_life_days", "pack_size"):
        if col in raw.columns:
            df[col] = _numeric(raw[col], comma)

    bad = df["business_date"].isna() | df["units_sold"].isna()
    bad |= (df["store_id"] == "") | (df["sku"] == "")
    if bad.sum() > 0.05 * len(df):
        raise IngestError(
            [
                f"{int(bad.sum())} of {len(df)} rows have an unreadable date, "
                "quantity, store or SKU; check the format (dd.mm.yyyy or yyyy-mm-dd)"
            ]
        )
    if bad.any():
        report.warnings.append(f"{int(bad.sum())} unreadable rows were dropped")
    df = df[~bad]
    neg = df["units_sold"] < 0
    if neg.any():
        report.warnings.append(f"{int(neg.sum())} rows with negative quantity dropped")
        df = df[~neg]
    if (df["units_sold"] % 1 != 0).any():
        report.warnings.append("fractional quantities were rounded to whole units")
    df["units_sold"] = df["units_sold"].round()

    if as_of is not None:
        df = df[df["business_date"] < pd.Timestamp(as_of)]
    if df.empty:
        raise IngestError(["no usable sales rows"])
    as_of_date = as_of or (df["business_date"].max() + pd.Timedelta(days=1)).date()

    meta_cols = [
        c
        for c in (
            "product_name",
            "category",
            "chain",
            "unit_price",
            "shelf_life_days",
            "pack_size",
        )
        if c in df
    ]
    meta = df.groupby(["store_id", "sku"])[meta_cols].last() if meta_cols else None
    keys = ["store_id", "sku", "business_date"]
    if df.duplicated(keys).any():
        report.warnings.append(
            f"{int(df.duplicated(keys).sum())} duplicate store/SKU/date rows "
            "were summed"
        )
    daily = df.groupby(keys, as_index=False)[["units_sold"]].sum()

    panel, filled = _fill_calendar(daily, as_of_date, report)
    if filled:
        report.warnings.append(
            f"{filled} missing trading days were filled with 0 sales; if they were "
            "stock-outs, true demand is higher than shown"
        )
    if meta is not None:
        panel = panel.merge(meta.reset_index(), on=["store_id", "sku"], how="left")
    report.date_from = panel["business_date"].min().date().isoformat()
    report.date_to = panel["business_date"].max().date().isoformat()
    report.rows_used = len(panel)
    report.series_used = panel.groupby(["store_id", "sku"]).ngroups
    if report.series_used > MAX_SERIES:
        raise IngestError(
            [
                f"{report.series_used} series exceed the limit of {MAX_SERIES}; "
                "split by store"
            ]
        )
    return panel, report, as_of_date


def _fill_calendar(
    daily: pd.DataFrame, as_of: date, report: QualityReport
) -> tuple[pd.DataFrame, int]:
    """Give every kept series a complete daily calendar with open/holiday flags."""
    last = pd.Timestamp(as_of) - pd.Timedelta(days=1)
    parts: list[pd.DataFrame] = []
    filled = 0
    for (store, sku), g in daily.groupby(["store_id", "sku"]):
        start, end = g["business_date"].min(), g["business_date"].max()
        days = (end - start).days + 1
        if days < MIN_HISTORY_DAYS:
            report.skipped.append(f"{store}/{sku}: only {days} days of history")
            continue
        if (last - end).days > STALE_DAYS:
            report.skipped.append(
                f"{store}/{sku}: no sales in the last {STALE_DAYS} days"
            )
            continue
        idx = pd.date_range(start, last, freq="D")
        full = g.set_index("business_date")["units_sold"].reindex(idx)
        country = _country(str(store))
        is_open = pd.Series([is_store_open(country, d.date()) for d in idx], index=idx)
        holiday = pd.Series([is_holiday(country, d.date()) for d in idx], index=idx)
        # Sales on a day the calendar says closed: treat the store as open that day.
        is_open = is_open | full.fillna(0).gt(0)
        filled += int((full.isna() & is_open).sum())
        out = pd.DataFrame(
            {
                "store_id": store,
                "sku": sku,
                "business_date": idx,
                "units_sold": full.fillna(0).astype(int).to_numpy(),
                "is_open": is_open.to_numpy(),
                "is_holiday": holiday.to_numpy(),
            }
        )
        parts.append(out)
    if not parts:
        raise IngestError(
            [
                "no series has enough recent history (need at least "
                f"{MIN_HISTORY_DAYS} days)"
            ]
            + report.skipped[:5]
        )
    return pd.concat(parts, ignore_index=True), filled


def clean_stock(raw: pd.DataFrame, as_of: date) -> tuple[pd.DataFrame, list[str]]:
    """Validate stock lots; return rows and warnings."""
    missing = [c for c in REQUIRED_STOCK if c not in raw.columns]
    if missing:
        raise IngestError([f"stock file: missing column(s): {', '.join(missing)}"])
    comma = bool(raw.attrs.get("decimal_comma", False))
    df = pd.DataFrame(
        {
            "store_id": raw["store_id"].str.strip(),
            "sku": raw["sku"].str.strip(),
            "quantity": _numeric(raw["quantity"], comma),
            "use_by_date": _parse_dates(raw["use_by_date"]),
        }
    )
    df["lot_id"] = raw["lot_id"].str.strip() if "lot_id" in raw.columns else ""
    warnings: list[str] = []
    bad = df["quantity"].isna() | (df["quantity"] < 0) | df["use_by_date"].isna()
    if bad.any():
        warnings.append(f"stock file: {int(bad.sum())} unreadable rows were dropped")
        df = df[~bad]
    expired = df["use_by_date"] < pd.Timestamp(as_of)
    if expired.any():
        warnings.append(
            f"stock file: {int(expired.sum())} lots already past use-by were ignored"
        )
        df = df[~expired]
    df["quantity"] = df["quantity"].round().astype(int)
    return df.reset_index(drop=True), warnings
