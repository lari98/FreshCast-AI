"""Bring-your-own-data: parsing, validation and the end-to-end forecast."""

from datetime import date

import pandas as pd
import pytest

from freshcast.byod.analyze import analyze
from freshcast.byod.ingest import (
    MAX_BYTES,
    IngestError,
    clean_sales,
    clean_stock,
    read_csv_bytes,
)


def _csv(sales: pd.DataFrame, **kw: object) -> bytes:
    return sales.to_csv(index=False, **kw).encode()  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def one_store(sales: pd.DataFrame) -> pd.DataFrame:
    s = sales[sales["store_id"] == "DE-MUC-001"]
    s = s[s["sku"].isin(["MILK-1L", "BREAD-WHEAT-750G"]) & s["is_open"]]
    return s[["store_id", "sku", "business_date", "units_sold"]]


def test_german_excel_format_is_parsed() -> None:
    raw = "﻿Filiale;Artikelnummer;Datum;Menge;Preis\nA;X;22.12.2025;5;1,50\n"
    df = read_csv_bytes(raw.encode("utf-8"))
    assert list(df.columns[:4]) == ["store_id", "sku", "business_date", "units_sold"]
    assert df.attrs["decimal_comma"] is True


def test_latin1_fallback_and_size_limit() -> None:
    df = read_csv_bytes(
        "store_id,sku,business_date,units_sold\nä,x,2025-01-01,1\n".encode("latin-1")
    )
    assert df.loc[0, "store_id"] == "ä"
    with pytest.raises(IngestError, match="larger"):
        read_csv_bytes(b"x" * (MAX_BYTES + 1))
    with pytest.raises(IngestError, match="header"):
        read_csv_bytes(b"just one column\n1\n")


def test_missing_columns_are_reported() -> None:
    raw = read_csv_bytes(b"store_id,sku\nA,B\n")
    with pytest.raises(IngestError, match="business_date"):
        clean_sales(raw)


def test_mostly_unreadable_rows_are_rejected() -> None:
    rows = "\n".join(f"A,B,not-a-date,{i}" for i in range(20))
    raw = read_csv_bytes(f"store_id,sku,business_date,units_sold\n{rows}\n".encode())
    with pytest.raises(IngestError, match="unreadable"):
        clean_sales(raw)


def test_repairs_are_reported(one_store: pd.DataFrame) -> None:
    data = one_store.copy()
    data.iloc[0, data.columns.get_loc("units_sold")] = -4  # type: ignore[index]
    data = pd.concat([data, data.iloc[[5]]])  # duplicate row
    data = data.drop(index=data.index[40:43])  # missing trading days
    raw = read_csv_bytes(_csv(data))
    _, report, as_of = clean_sales(raw)
    text = " ".join(report.warnings)
    assert "negative" in text and "duplicate" in text and "missing trading days" in text
    assert report.series_used == 2 and as_of > date(2025, 7, 1)


def test_short_history_is_skipped_not_forecast(one_store: pd.DataFrame) -> None:
    short = one_store[one_store["business_date"] > date(2025, 6, 25)]
    with pytest.raises(IngestError, match="enough recent history"):
        clean_sales(read_csv_bytes(_csv(short)))


def test_stock_validation(one_store: pd.DataFrame) -> None:
    raw = read_csv_bytes(
        b"store_id,sku,quantity,use_by_date\nA,B,5,2025-12-30\nA,B,x,2025-12-31\nA,B,7,2026-01-05\n"
    )
    lots, warnings = clean_stock(raw, date(2026, 1, 1))
    assert len(lots) == 1 and lots.loc[0, "quantity"] == 7
    assert len(warnings) == 2
    with pytest.raises(IngestError, match="use_by_date"):
        clean_stock(read_csv_bytes(b"store_id,sku,quantity\nA,B,1\n"), date(2026, 1, 1))


def test_end_to_end_payload_matches_dashboard_contract(one_store: pd.DataFrame) -> None:
    stock = b"store_id,sku,quantity,use_by_date\nDE-MUC-001,MILK-1L,30,2026-01-30\n"
    last = one_store["business_date"].max()
    payload = analyze(_csv(one_store), stock)
    assert payload["source"] == "upload" and len(payload["items"]) == 2
    item = payload["items"][0]
    assert item["currency"] == "EUR" and len(item["series"]) == 21
    assert item["series"][-1]["actual"] is None  # future days have no actuals
    assert item["series"][0]["actual"] is not None
    assert item["proposal"]["recommended_order_units"] >= 0
    assert "uploaded data" in payload["disclaimer"]
    assert pd.Timestamp(payload["as_of"]) == pd.Timestamp(last) + pd.Timedelta(days=1)
    assert payload["quality"]["series_used"] == 2


def test_no_stock_file_is_flagged(one_store: pd.DataFrame) -> None:
    payload = analyze(_csv(one_store))
    assert any("no stock file" in w for w in payload["quality"]["warnings"])
    assert all(i["lots"] == [] for i in payload["items"])


def test_chain_column_is_read_with_german_alias(one_store: pd.DataFrame) -> None:
    with_chain = one_store.assign(Handelskette="Beispielkette")
    payload = analyze(_csv(with_chain))
    assert {i["chain"] for i in payload["items"]} == {"Beispielkette"}


def test_chain_is_optional(one_store: pd.DataFrame) -> None:
    payload = analyze(_csv(one_store))
    assert {i["chain"] for i in payload["items"]} == {""}
