"""Day-by-day FEFO simulation and cost-based order planning.

Why simulate?
-------------
The simple engine (``engine.py``) compares one target with one stock number.
Real perishables need the *timeline*: lots expire on different days, deliveries
arrive on schedule, and the oldest stock is sold first (FEFO: first expired,
first out). This module simulates that timeline under three demand scenarios
(lower / point / upper forecast) and picks the order quantity with the lowest
expected cost, balancing waste against lost sales.

Safety rules
------------
* Blocked lots (hold/recall) are never sold and never counted as waste.
* The result is a *proposal*; ``requires_human_approval`` is always True.
* All arithmetic is integer; the planner is deterministic and auditable.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from freshcast.replenishment.engine import StockLot

SCENARIOS = ("lower", "point", "upper")


@dataclass(frozen=True, slots=True)
class Delivery:
    """A confirmed inbound lot."""

    lot_id: str
    arrival_date: date
    quantity: int
    use_by_date: date  # last day the lot may be sold (inclusive)

    def __post_init__(self) -> None:
        """Validate quantity and dates."""
        if not self.lot_id.strip():
            raise ValueError("lot_id must not be blank")
        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")
        if self.use_by_date < self.arrival_date:
            raise ValueError("delivery expires before it arrives")


@dataclass(frozen=True, slots=True)
class DemandScenarios:
    """Per-day unit demand for the planning horizon, three scenarios."""

    lower: tuple[int, ...]
    point: tuple[int, ...]
    upper: tuple[int, ...]

    def __post_init__(self) -> None:
        """Require equal lengths, non-negative values and lower <= point <= upper."""
        if not (len(self.lower) == len(self.point) == len(self.upper)):
            raise ValueError("scenarios must have equal length")
        if not self.point:
            raise ValueError("horizon must contain at least one day")
        for lo, mid, hi in zip(self.lower, self.point, self.upper, strict=True):
            if lo < 0 or not lo <= mid <= hi:
                raise ValueError("require 0 <= lower <= point <= upper per day")

    @classmethod
    def from_floats(
        cls,
        lower: Sequence[float],
        point: Sequence[float],
        upper: Sequence[float],
    ) -> DemandScenarios:
        """Round model output to whole units (lower down, upper up)."""
        return cls(
            lower=tuple(math.floor(x) for x in lower),
            point=tuple(round(x) for x in point),
            upper=tuple(math.ceil(x) for x in upper),
        )

    def series(self, name: str) -> tuple[int, ...]:
        """Return one scenario by name."""
        return getattr(self, name)  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    """Result of simulating one demand series."""

    sold_units: int
    lost_units: int  # unmet demand (stock-out)
    waste_units: int  # expired before sale
    end_stock_units: int
    blocked_units: int  # held/recalled, excluded from everything above


@dataclass(slots=True)
class _Batch:
    use_by: date
    quantity: int


def simulate(
    as_of: date,
    lots: Sequence[StockLot],
    deliveries: Sequence[Delivery],
    demand: Sequence[int],
) -> SimulationOutcome:
    """Simulate daily FEFO sales; day 0 is ``as_of``.

    Each day: receive deliveries, write off lots whose use-by date has passed,
    then sell oldest-first. Deliveries arriving after the horizon are ignored.
    """
    if any(d < 0 for d in demand):
        raise ValueError("demand cannot be negative")
    stock = [_Batch(lot.use_by_date, lot.quantity) for lot in lots if not lot.blocked]
    blocked = sum(lot.quantity for lot in lots if lot.blocked)
    for delivery in deliveries:
        if delivery.arrival_date < as_of:
            raise ValueError("delivery arrival is before the planning start")

    sold = lost = waste = 0
    for offset, need in enumerate(demand):
        today = as_of + timedelta(days=offset)
        stock += [
            _Batch(d.use_by_date, d.quantity)
            for d in deliveries
            if d.arrival_date == today
        ]
        waste += sum(b.quantity for b in stock if b.use_by < today)
        stock = [b for b in stock if b.use_by >= today]
        stock.sort(key=lambda b: b.use_by)  # FEFO
        remaining = need
        for batch in stock:
            take = min(batch.quantity, remaining)
            batch.quantity -= take
            remaining -= take
        stock = [b for b in stock if b.quantity > 0]
        sold += need - remaining
        lost += remaining
    return SimulationOutcome(
        sold_units=sold,
        lost_units=lost,
        waste_units=waste,
        end_stock_units=sum(b.quantity for b in stock),
        blocked_units=blocked,
    )


def next_delivery_date(
    as_of: date, lead_days: int, delivery_weekdays: frozenset[int]
) -> date:
    """Return the first allowed delivery day on or after ``as_of + lead_days``."""
    if lead_days < 0:
        raise ValueError("lead_days cannot be negative")
    if not delivery_weekdays or not delivery_weekdays <= set(range(7)):
        raise ValueError("delivery_weekdays must be a non-empty subset of 0..6")
    day = as_of + timedelta(days=lead_days)
    while day.weekday() not in delivery_weekdays:
        day += timedelta(days=1)
    return day


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    """Inputs for one store/SKU order plan."""

    store_id: str
    sku: str
    as_of_date: date
    scenarios: DemandScenarios
    stock_lots: tuple[StockLot, ...]
    deliveries: tuple[Delivery, ...]
    supplier_lead_days: int
    delivery_weekdays: frozenset[int]
    order_multiple: int
    remaining_shelf_life_days: int  # sellable days after arrival (use-by inclusive)
    unit_cost: float  # cost of one wasted unit
    unit_margin: float  # profit lost per unit of unmet demand
    scenario_weights: tuple[float, float, float] = (0.2, 0.6, 0.2)
    # Proxy for future waste of stock left over after the horizon.
    leftover_cost_factor: float = 0.3

    def __post_init__(self) -> None:
        """Validate business parameters."""
        if not self.store_id.strip() or not self.sku.strip():
            raise ValueError("store_id and sku are required")
        if self.order_multiple <= 0:
            raise ValueError("order_multiple must be positive")
        if self.remaining_shelf_life_days < 0:
            raise ValueError("remaining_shelf_life_days cannot be negative")
        if self.unit_cost < 0 or self.unit_margin < 0:
            raise ValueError("costs cannot be negative")
        if not math.isclose(sum(self.scenario_weights), 1.0) or any(
            w < 0 for w in self.scenario_weights
        ):
            raise ValueError("scenario_weights must be non-negative and sum to 1")


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    """Auditable plan; never places an order by itself."""

    sku: str
    recommended_order_units: int
    arrival_date: date
    expected_cost: float
    outcomes: dict[str, SimulationOutcome]  # outcome of the chosen quantity
    requires_human_approval: bool = True


def _expected_cost(
    req: PlanningRequest, outcomes: dict[str, SimulationOutcome]
) -> float:
    total = 0.0
    for weight, name in zip(req.scenario_weights, SCENARIOS, strict=True):
        o = outcomes[name]
        total += weight * (
            o.waste_units * req.unit_cost
            + o.lost_units * req.unit_margin
            + o.end_stock_units * req.unit_cost * req.leftover_cost_factor
        )
    return total


def plan_order(req: PlanningRequest) -> PlanningDecision:
    """Pick the pack-rounded order quantity with the lowest expected cost."""
    horizon = len(req.scenarios.point)
    arrival = next_delivery_date(
        req.as_of_date, req.supplier_lead_days, req.delivery_weekdays
    )
    if (arrival - req.as_of_date).days >= horizon:
        raise ValueError("planning horizon ends before the earliest delivery")
    use_by = arrival + timedelta(days=req.remaining_shelf_life_days)
    # More than the upper-scenario demand can never help; cap the search there.
    cap_units = sum(req.scenarios.upper)
    max_packs = math.ceil(cap_units / req.order_multiple)

    best: tuple[float, int, dict[str, SimulationOutcome]] | None = None
    for packs in range(max_packs + 1):
        qty = packs * req.order_multiple
        new_delivery = Delivery("PLANNED-ORDER", arrival, qty, use_by)
        outcomes = {
            name: simulate(
                req.as_of_date,
                req.stock_lots,
                (*req.deliveries, new_delivery),
                req.scenarios.series(name),
            )
            for name in SCENARIOS
        }
        cost = _expected_cost(req, outcomes)
        if best is None or cost < best[0] - 1e-9:  # ties keep the smaller order
            best = (cost, qty, outcomes)
    if best is None:  # unreachable: range(max_packs + 1) is never empty
        raise RuntimeError("no candidate order evaluated")
    cost, qty, outcomes = best
    return PlanningDecision(
        sku=req.sku,
        recommended_order_units=qty,
        arrival_date=arrival,
        expected_cost=round(cost, 2),
        outcomes=outcomes,
    )
