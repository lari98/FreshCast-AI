"""Deterministic, expiry-aware replenishment proposals.

Design notes
------------
* Pure business logic: no AWS, database or ML imports, so it can be unit
  tested offline and reused from Lambda, FastAPI or SageMaker jobs.
* The ML model supplies *demand*; this module turns demand into an order
  proposal. Generative AI never decides quantities (see ADR 0002).
* The result is a *proposal*. A human must approve it, and food-safety
  holds or recalls always take precedence over commercial logic.

Known simplification (v0.1)
---------------------------
Stock that expires before the delivery date is excluded, but daily sales
between today and arrival are not simulated. A later release will replace
this with a day-by-day depletion model (FEFO, delivery schedules).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal


@dataclass(frozen=True, slots=True)
class StockLot:
    """Inventory belonging to one traceable lot (EC 178/2002, Art. 18)."""

    lot_id: str
    quantity: int
    use_by_date: date
    # Food-safety hold or recall: blocked stock is never sellable, whatever
    # the forecast says (safety always overrides commercial logic).
    blocked: bool = False

    def __post_init__(self) -> None:
        """Reject malformed lots at the boundary."""
        if not self.lot_id.strip():
            raise ValueError("lot_id must not be blank")
        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")


@dataclass(frozen=True, slots=True)
class ReplenishmentRequest:
    """Validated inputs for one store/SKU order proposal."""

    store_id: str
    sku: str
    as_of_date: date
    forecast_units: int  # expected demand in the ordering window
    safety_stock_units: int  # buffer derived from forecast uncertainty
    incoming_units: int  # confirmed inbound units within the window
    supplier_lead_days: int  # days between ordering and arrival
    order_multiple: int  # supplier pack size; orders are whole packs
    stock_lots: tuple[StockLot, ...]

    def __post_init__(self) -> None:
        """Validate identifiers and numeric ranges."""
        if not self.store_id.strip() or not self.sku.strip():
            raise ValueError("store_id and sku are required")
        non_negative = {
            "forecast_units": self.forecast_units,
            "safety_stock_units": self.safety_stock_units,
            "incoming_units": self.incoming_units,
            "supplier_lead_days": self.supplier_lead_days,
        }
        for name, value in non_negative.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.order_multiple <= 0:
            raise ValueError("order_multiple must be positive")


@dataclass(frozen=True, slots=True)
class ReplenishmentDecision:
    """Auditable output; never places an order by itself."""

    sku: str
    usable_stock_units: int
    expiring_stock_units: int
    target_stock_units: int
    recommended_order_units: int
    requires_human_approval: bool = True


def calculate_replenishment(request: ReplenishmentRequest) -> ReplenishmentDecision:
    """Calculate a pack-rounded order proposal for one store and SKU."""
    arrival_date = request.as_of_date + timedelta(days=request.supplier_lead_days)

    # Lots whose use-by date falls before arrival cannot be sold from the
    # replenished shelf, so they must not reduce the order quantity.
    sellable = [lot for lot in request.stock_lots if not lot.blocked]
    usable = sum(lot.quantity for lot in sellable if lot.use_by_date >= arrival_date)
    expiring = sum(lot.quantity for lot in sellable if lot.use_by_date < arrival_date)

    target = request.forecast_units + request.safety_stock_units
    shortage = max(0, target - usable - request.incoming_units)

    # Decimal avoids floating-point surprises at pack-size boundaries.
    packs = (Decimal(shortage) / Decimal(request.order_multiple)).to_integral_value(
        rounding=ROUND_CEILING
    )

    return ReplenishmentDecision(
        sku=request.sku,
        usable_stock_units=usable,
        expiring_stock_units=expiring,
        target_stock_units=target,
        recommended_order_units=int(packs) * request.order_multiple,
    )
