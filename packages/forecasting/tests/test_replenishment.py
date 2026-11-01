"""Business-invariant tests for the replenishment engine."""

from datetime import date, timedelta

import pytest

from freshcast.replenishment.engine import (
    ReplenishmentRequest,
    StockLot,
    calculate_replenishment,
)

TODAY = date(2026, 11, 1)


def _request(**overrides: object) -> ReplenishmentRequest:
    base: dict[str, object] = {
        "store_id": "DE-MUC-001",
        "sku": "STRAWBERRY-500G",
        "as_of_date": TODAY,
        "forecast_units": 120,
        "safety_stock_units": 20,
        "incoming_units": 10,
        "supplier_lead_days": 2,
        "order_multiple": 12,
        "stock_lots": (
            StockLot("LOT-A", 30, TODAY + timedelta(days=1)),
            StockLot("LOT-B", 40, TODAY + timedelta(days=4)),
        ),
    }
    base.update(overrides)
    return ReplenishmentRequest(**base)  # type: ignore[arg-type]


def test_order_respects_expiry_and_pack_size() -> None:
    result = calculate_replenishment(_request())
    assert result.usable_stock_units == 40
    assert result.expiring_stock_units == 30
    assert result.target_stock_units == 140
    assert result.recommended_order_units == 96  # shortage 90 -> 8 packs of 12
    assert result.requires_human_approval is True


def test_no_order_when_stock_is_sufficient() -> None:
    req = _request(
        store_id="AT-VIE-001",
        sku="MILK-1L",
        forecast_units=50,
        safety_stock_units=5,
        incoming_units=0,
        supplier_lead_days=1,
        order_multiple=6,
        stock_lots=(StockLot("LOT-C", 80, TODAY + timedelta(days=5)),),
    )
    assert calculate_replenishment(req).recommended_order_units == 0


def test_lot_expiring_on_arrival_day_is_still_usable() -> None:
    req = _request(stock_lots=(StockLot("L", 10, TODAY + timedelta(days=2)),))
    assert calculate_replenishment(req).usable_stock_units == 10


@pytest.mark.parametrize(
    "field",
    ["forecast_units", "safety_stock_units", "incoming_units", "supplier_lead_days"],
)
def test_negative_request_values_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        _request(**{field: -1})


def test_invalid_pack_size_rejected() -> None:
    with pytest.raises(ValueError, match="order_multiple"):
        _request(order_multiple=0)


def test_blank_identifiers_rejected() -> None:
    with pytest.raises(ValueError, match="required"):
        _request(sku=" ")


def test_negative_stock_is_rejected() -> None:
    with pytest.raises(ValueError, match="quantity"):
        StockLot("INVALID", -1, TODAY)


def test_blank_lot_id_rejected() -> None:
    with pytest.raises(ValueError, match="lot_id"):
        StockLot(" ", 1, TODAY)
