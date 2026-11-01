"""FEFO simulation and order-planner behaviour."""

from datetime import date, timedelta

import pytest

from freshcast.replenishment.engine import StockLot
from freshcast.replenishment.planner import (
    Delivery,
    DemandScenarios,
    PlanningRequest,
    next_delivery_date,
    plan_order,
    simulate,
)

D0 = date(2026, 11, 2)  # Monday


def _lot(lot_id: str, qty: int, days: int, blocked: bool = False) -> StockLot:
    return StockLot(lot_id, qty, D0 + timedelta(days=days), blocked)


def test_fefo_sells_oldest_lot_first() -> None:
    lots = [_lot("NEW", 10, 5), _lot("OLD", 10, 1)]
    # Day 0 sells 10 (all OLD). Day 2: OLD would have expired but is gone.
    out = simulate(D0, lots, [], [10, 0, 5])
    assert (out.sold_units, out.waste_units, out.end_stock_units) == (15, 0, 5)


def test_unsold_stock_expires_as_waste() -> None:
    out = simulate(D0, [_lot("A", 10, 1)], [], [2, 2, 2, 2])
    assert out.waste_units == 6  # 4 sold on days 0-1, 6 expire on day 2
    assert out.sold_units == 4
    assert out.lost_units == 4  # days 2-3 demand cannot be met


def test_blocked_lot_is_never_sold_or_wasted() -> None:
    out = simulate(D0, [_lot("RECALL", 100, 5, blocked=True)], [], [10, 10])
    assert (out.sold_units, out.lost_units, out.waste_units) == (0, 20, 0)
    assert out.blocked_units == 100


def test_delivery_arrives_on_schedule() -> None:
    delivery = Delivery("D1", D0 + timedelta(days=2), 20, D0 + timedelta(days=6))
    out = simulate(D0, [], [delivery], [5, 5, 5, 5])
    assert (out.lost_units, out.sold_units) == (10, 10)


def test_conservation_of_units() -> None:
    lots = [_lot("A", 30, 2), _lot("B", 50, 6)]
    delivery = Delivery("D", D0 + timedelta(days=1), 40, D0 + timedelta(days=3))
    out = simulate(D0, lots, [delivery], [12, 9, 15, 8, 20, 4])
    assert out.sold_units + out.waste_units + out.end_stock_units == 30 + 50 + 40


def test_simulation_validation() -> None:
    with pytest.raises(ValueError, match="negative"):
        simulate(D0, [], [], [-1])
    late = Delivery("D", D0 - timedelta(days=1), 1, D0)
    with pytest.raises(ValueError, match="before the planning start"):
        simulate(D0, [], [late], [1])


def test_delivery_validation() -> None:
    with pytest.raises(ValueError, match="expires before"):
        Delivery("D", D0, 1, D0 - timedelta(days=1))
    with pytest.raises(ValueError, match="negative"):
        Delivery("D", D0, -1, D0)
    with pytest.raises(ValueError, match="lot_id"):
        Delivery(" ", D0, 1, D0)


def test_next_delivery_date_respects_weekdays() -> None:
    tue_thu_sat = frozenset({1, 3, 5})
    assert next_delivery_date(D0, 0, tue_thu_sat) == D0 + timedelta(days=1)
    assert next_delivery_date(D0, 2, tue_thu_sat) == D0 + timedelta(days=3)
    with pytest.raises(ValueError, match="delivery_weekdays"):
        next_delivery_date(D0, 1, frozenset())
    with pytest.raises(ValueError, match="lead_days"):
        next_delivery_date(D0, -1, tue_thu_sat)


def test_scenarios_validation_and_rounding() -> None:
    with pytest.raises(ValueError, match="equal length"):
        DemandScenarios((1,), (1, 2), (1, 2))
    with pytest.raises(ValueError, match="lower <= point"):
        DemandScenarios((5,), (4,), (6,))
    with pytest.raises(ValueError, match="at least one day"):
        DemandScenarios((), (), ())
    s = DemandScenarios.from_floats([3.9], [4.4], [5.1])
    assert (s.lower, s.point, s.upper) == ((3,), (4,), (6,))


def _request(**overrides: object) -> PlanningRequest:
    scen = DemandScenarios(
        lower=(8, 8, 8, 8, 8, 8),
        point=(10, 10, 10, 10, 10, 10),
        upper=(14, 14, 14, 14, 14, 14),
    )
    base: dict[str, object] = {
        "store_id": "DE-MUC-001",
        "sku": "MILK-1L",
        "as_of_date": D0,
        "scenarios": scen,
        "stock_lots": (),
        "deliveries": (),
        "supplier_lead_days": 1,
        "delivery_weekdays": frozenset(range(6)),
        "order_multiple": 6,
        "remaining_shelf_life_days": 5,
        "unit_cost": 1.0,
        "unit_margin": 1.0,
    }
    base.update(overrides)
    return PlanningRequest(**base)  # type: ignore[arg-type]


def test_empty_shelf_triggers_pack_rounded_order() -> None:
    plan = plan_order(_request())
    assert plan.recommended_order_units > 0
    assert plan.recommended_order_units % 6 == 0
    assert plan.arrival_date == D0 + timedelta(days=1)
    assert plan.requires_human_approval is True


def test_no_order_when_stock_covers_upper_scenario() -> None:
    lots = (_lot("BIG", 200, 20),)
    assert plan_order(_request(stock_lots=lots)).recommended_order_units == 0


def test_blocked_stock_does_not_prevent_ordering() -> None:
    lots = (_lot("RECALL", 500, 20, blocked=True),)
    assert plan_order(_request(stock_lots=lots)).recommended_order_units > 0


def test_expensive_stockouts_increase_the_order() -> None:
    cheap = plan_order(_request(unit_margin=0.1, unit_cost=2.0))
    dear = plan_order(_request(unit_margin=5.0, unit_cost=0.5))
    assert dear.recommended_order_units > cheap.recommended_order_units


def test_short_shelf_life_limits_the_order() -> None:
    long_life = plan_order(_request(remaining_shelf_life_days=10))
    short_life = plan_order(_request(remaining_shelf_life_days=1))
    assert short_life.recommended_order_units <= long_life.recommended_order_units


def test_horizon_before_delivery_rejected() -> None:
    with pytest.raises(ValueError, match="horizon ends"):
        plan_order(
            _request(
                supplier_lead_days=6, delivery_weekdays=frozenset({0, 1, 2, 3, 4, 5, 6})
            )
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("store_id", " ", "required"),
        ("order_multiple", 0, "order_multiple"),
        ("remaining_shelf_life_days", -1, "shelf_life"),
        ("unit_cost", -1.0, "costs"),
        ("scenario_weights", (0.5, 0.5, 0.5), "sum to 1"),
    ],
)
def test_request_validation(field: str, value: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _request(**{field: value})
