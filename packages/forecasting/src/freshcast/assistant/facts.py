"""Structured facts: the only information the language model may use."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import date, timedelta
from decimal import Decimal

from freshcast.replenishment.engine import ReplenishmentDecision, ReplenishmentRequest

# Identifier digits (store/SKU) are trusted; free-text names only contribute
# pack-size numbers that carry a unit ("500 g"), never arbitrary digits.
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s?(?:kg|g|ml|cl|l|stk|st)\b", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>{}\[\]`]")


def sanitize_text(value: str, limit: int = 80) -> str:
    """Neutralise free text before it enters a prompt (injection hygiene)."""
    return re.sub(r"\s+", " ", _CONTROL.sub(" ", value)).strip()[:limit]


@dataclass(frozen=True, slots=True)
class ExplanationFacts:
    """Everything an explanation may state, computed by deterministic code."""

    store_id: str
    sku: str
    product_name: str
    as_of_date: date
    arrival_date: date
    forecast_units: int
    safety_stock_units: int
    incoming_units: int
    usable_stock_units: int
    expiring_stock_units: int
    blocked_units: int
    target_stock_units: int
    recommended_order_units: int
    order_multiple: int
    supplier_lead_days: int
    requires_human_approval: bool = True

    @classmethod
    def from_replenishment(
        cls,
        request: ReplenishmentRequest,
        decision: ReplenishmentDecision,
        product_name: str,
    ) -> ExplanationFacts:
        """Build facts from a validated request and its decision."""
        return cls(
            store_id=request.store_id,
            sku=request.sku,
            product_name=sanitize_text(product_name),
            as_of_date=request.as_of_date,
            arrival_date=request.as_of_date
            + timedelta(days=request.supplier_lead_days),
            forecast_units=request.forecast_units,
            safety_stock_units=request.safety_stock_units,
            incoming_units=request.incoming_units,
            usable_stock_units=decision.usable_stock_units,
            expiring_stock_units=decision.expiring_stock_units,
            blocked_units=sum(
                lot.quantity for lot in request.stock_lots if lot.blocked
            ),
            target_stock_units=decision.target_stock_units,
            recommended_order_units=decision.recommended_order_units,
            order_multiple=request.order_multiple,
            supplier_lead_days=request.supplier_lead_days,
            requires_human_approval=decision.requires_human_approval,
        )

    def as_dict(self) -> dict[str, object]:
        """Return JSON-friendly values for the prompt."""
        out: dict[str, object] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = value.isoformat() if isinstance(value, date) else value
        return out

    def allowed_numbers(self) -> set[Decimal]:
        """Return every number an answer may legitimately contain."""
        allowed: set[Decimal] = set()
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                allowed.add(Decimal(str(value)))
            elif isinstance(value, date):
                allowed.update(Decimal(p) for p in (value.year, value.month, value.day))
        for identifier in (self.store_id, self.sku):  # e.g. "STRAWBERRY-500G"
            allowed.update(Decimal(m) for m in re.findall(r"\d+", identifier))
        for match in _SIZE.finditer(self.product_name):
            allowed.add(Decimal(match.group(1).replace(",", ".")))
        return allowed
