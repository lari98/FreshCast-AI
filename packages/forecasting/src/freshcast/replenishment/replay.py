"""Policy replay: what would each ordering policy have done over 3 months.

The replay walks forward day by day over *recorded* history. For every
store/SKU and delivery day it asks each policy for an order using only what was
known at the time (model trained on earlier data, features lagged by the
forecast horizon, stock on hand), then plays out the real sales against that
stock with FEFO and counts waste, lost sales and profit.

Policies compared
-----------------
``naive``       same weekday last week, no safety stock (a common manual habit)
``rule_v1``     LightGBM point forecast + safety stock (the shipped v1 engine)
``newsvendor``  LightGBM + critical-ratio target from the interval (this phase)
``planner``     expected-cost minimum over lower/point/upper scenarios (FEFO)

Honest limits
-------------
* Data is synthetic and recorded sales equal demand (no censoring), so the
  numbers show the *mechanics*, not savings you would get in a real store.
* Cost is 60 % and margin 40 % of the list price (an assumption, stated in the
  report). Promotions change revenue, not the purchase cost.
* The forecast for the 3rd covered day (only around holidays) uses sales up to
  the order day: a small look-ahead that happens on a few days per year.
* Each delivery covers the days until the next delivery. The first week is a
  warm-up from empty shelves and is excluded from every metric.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from freshcast.data.synthetic import PRODUCTS, STORES
from freshcast.domain.entities import Product
from freshcast.features.builder import build_features
from freshcast.models.baseline import seasonal_naive
from freshcast.models.lgbm import DemandForecaster
from freshcast.replenishment.engine import (
    ReplenishmentRequest,
    StockLot,
    calculate_replenishment,
)
from freshcast.replenishment.newsvendor import critical_ratio, newsvendor_target
from freshcast.replenishment.planner import DemandScenarios, PlanningRequest, plan_order

CHAINS = {store.store_id: store.chain for store in STORES}
POLICIES = ("naive", "rule_v1", "newsvendor", "planner")
COST_SHARE = 0.6
MARGIN_SHARE = 0.4
CHF_PRICE_FACTOR = 1.15
MAX_COVER_DAYS = 3


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    """Replay window and model settings."""

    start: date  # first counted day
    days: int = 92
    warmup_days: int = 7
    retrain_every_days: int = 30
    horizon: int = 2
    calibration_days: int = 28
    stores: tuple[str, ...] = ()  # empty = all stores
    skus: tuple[str, ...] = ()  # empty = all products
    # Share of a leftover unit's cost that is really lost, per SKU (1.0 = all).
    # Leftovers that can be sold tomorrow are not waste yet; see tune_overage().
    overage_factors: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the window."""
        if self.days <= 0 or self.warmup_days < 0 or self.retrain_every_days <= 0:
            raise ValueError("days and retrain_every_days must be positive")


@dataclass(slots=True)
class _Series:
    """Everything one store/SKU needs during the replay (aligned by day)."""

    store_id: str
    sku: str
    product: Product
    currency: str
    dates: list[date]
    is_open: list[bool]
    demand: list[int]
    price: list[float]
    point: list[float]
    lower: list[float]
    upper: list[float]
    naive: list[float]
    cost: float = 0.0
    margin: float = 0.0
    ratio: float = 0.5
    overage: float = 1.0


@dataclass(slots=True)
class _Stock:
    lots: list[list[Any]] = field(default_factory=list)  # [use_by, quantity]

    def usable(self, day: date) -> int:
        return sum(q for u, q in self.lots if u >= day)

    def as_lots(self, day: date) -> tuple[StockLot, ...]:
        live = [(u, q) for u, q in self.lots if u >= day and q > 0]
        return tuple(StockLot(f"L{i}", q, u) for i, (u, q) in enumerate(live))


# ---------------------------------------------------------------- forecasts
def build_forecasts(sales: pd.DataFrame, cfg: ReplayConfig) -> pd.DataFrame:
    """Point/interval/naive forecasts for every simulated day (walk-forward).

    The model is refitted every ``retrain_every_days`` on rows that end
    ``horizon`` days before the block starts, exactly like a rolling backtest.
    """
    feats = build_features(sales, cfg.horizon)
    sim_start = pd.Timestamp(cfg.start - timedelta(days=cfg.warmup_days))
    sim_end = pd.Timestamp(cfg.start + timedelta(days=cfg.days))
    parts: list[pd.DataFrame] = []
    block = sim_start
    while block < sim_end:
        block_end = min(block + pd.Timedelta(days=cfg.retrain_every_days), sim_end)
        train = feats[feats["business_date"] < block - pd.Timedelta(days=cfg.horizon)]
        model = DemandForecaster(calibration_days=cfg.calibration_days).fit(train)
        rows = feats[
            (feats["business_date"] >= block) & (feats["business_date"] < block_end)
        ].copy()
        rows[["point", "lower", "upper"]] = model.predict(rows)
        rows["naive"] = seasonal_naive(rows)
        parts.append(rows)
        block = block_end
    return pd.concat(parts, ignore_index=True)


def _make_series(forecasts: pd.DataFrame, cfg: ReplayConfig) -> list[_Series]:
    products = {p.sku: p for p in PRODUCTS}
    out: list[_Series] = []
    for (store_id, sku), g in forecasts.groupby(["store_id", "sku"], sort=True):
        if cfg.stores and store_id not in cfg.stores:
            continue
        if cfg.skus and sku not in cfg.skus:
            continue
        g = g.sort_values("business_date")
        product = products[str(sku)]
        currency = str(g["currency"].iloc[0])
        list_price = product.base_price_eur * (
            CHF_PRICE_FACTOR if currency == "CHF" else 1.0
        )
        s = _Series(
            store_id=str(store_id),
            sku=str(sku),
            product=product,
            currency=currency,
            dates=[d.date() for d in g["business_date"]],
            is_open=g["is_open"].astype(bool).tolist(),
            demand=g["units_sold"].astype(int).tolist(),
            price=g["unit_price"].astype(float).tolist(),
            point=g["point"].astype(float).tolist(),
            lower=g["lower"].astype(float).tolist(),
            upper=g["upper"].astype(float).tolist(),
            naive=g["naive"].astype(float).tolist(),
            cost=list_price * COST_SHARE,
            margin=list_price * MARGIN_SHARE,
        )
        s.overage = cfg.overage_factors.get(s.sku, 1.0)
        s.ratio = critical_ratio(s.cost, s.margin, s.overage)
        out.append(s)
    return out


# ---------------------------------------------------------------- policies
Decide = Callable[[_Series, int, int, _Stock], int]


def _engine_order(
    s: _Series, arrival: date, forecast: int, safety: int, stock: _Stock
) -> int:
    request = ReplenishmentRequest(
        store_id=s.store_id,
        sku=s.sku,
        as_of_date=arrival - timedelta(days=1),
        forecast_units=forecast,
        safety_stock_units=safety,
        incoming_units=0,
        supplier_lead_days=1,
        order_multiple=s.product.pack_size,
        stock_lots=stock.as_lots(arrival - timedelta(days=1)),
    )
    return calculate_replenishment(request).recommended_order_units


def _decide_naive(s: _Series, i: int, j: int, stock: _Stock) -> int:
    target = round(sum(s.naive[i:j]))
    return _engine_order(s, s.dates[i], target, 0, stock)


def _decide_rule(s: _Series, i: int, j: int, stock: _Stock) -> int:
    scen = DemandScenarios.from_floats(s.lower[i:j], s.point[i:j], s.upper[i:j])
    forecast = sum(scen.point)
    safety = max(0, sum(scen.upper) - forecast)
    return _engine_order(s, s.dates[i], forecast, safety, stock)


def _decide_newsvendor(s: _Series, i: int, j: int, stock: _Stock) -> int:
    target = newsvendor_target(s.point[i:j], s.lower[i:j], s.upper[i:j], s.ratio)
    return _engine_order(s, s.dates[i], math.ceil(target), 0, stock)


def _decide_planner(s: _Series, i: int, j: int, stock: _Stock) -> int:
    arrival = s.dates[i]
    as_of = arrival - timedelta(days=1)
    scen = DemandScenarios.from_floats(
        [0.0, *s.lower[i:j]], [0.0, *s.point[i:j]], [0.0, *s.upper[i:j]]
    )
    plan = plan_order(
        PlanningRequest(
            store_id=s.store_id,
            sku=s.sku,
            as_of_date=as_of,
            scenarios=scen,
            stock_lots=stock.as_lots(as_of),
            deliveries=(),
            supplier_lead_days=1,
            delivery_weekdays=frozenset({arrival.weekday()}),
            order_multiple=s.product.pack_size,
            remaining_shelf_life_days=max(1, s.product.shelf_life_days - 1),
            unit_cost=s.cost,
            unit_margin=s.margin,
            leftover_cost_factor=min(1.0, s.overage),
        )
    )
    return plan.recommended_order_units


DECIDERS: dict[str, Decide] = {
    "naive": _decide_naive,
    "rule_v1": _decide_rule,
    "newsvendor": _decide_newsvendor,
    "planner": _decide_planner,
}


# --------------------------------------------------------------- simulation
def _arrival_days(s: _Series) -> list[int]:
    """Return indices of delivery days: trading days Monday to Saturday."""
    return [i for i, d in enumerate(s.dates) if s.is_open[i] and d.weekday() < 6]


def simulate_policy(s: _Series, policy: str) -> pd.DataFrame:
    """Play one policy over one series; one row per simulated day."""
    decide = DECIDERS[policy]
    arrivals = _arrival_days(s)
    arrival_set = set(arrivals)
    next_after = {
        arrivals[k]: arrivals[k + 1] if k + 1 < len(arrivals) else len(s.dates)
        for k in range(len(arrivals))
    }
    shelf = max(1, s.product.shelf_life_days - 1)
    stock = _Stock()
    pending: dict[int, int] = {}
    rows: list[dict[str, Any]] = []
    for i, day in enumerate(s.dates):
        received = pending.pop(i, 0)
        if received:
            stock.lots.append([day + timedelta(days=shelf), received])
        waste = sum(q for u, q in stock.lots if u < day)
        stock.lots = [[u, q] for u, q in stock.lots if u >= day]
        stock.lots.sort(key=lambda lot: lot[0])  # FEFO
        need = s.demand[i] if s.is_open[i] else 0
        left = need
        for lot in stock.lots:
            take = min(lot[1], left)
            lot[1] -= take
            left -= take
        stock.lots = [lot for lot in stock.lots if lot[1] > 0]
        rows.append(
            {
                "policy": policy,
                "store_id": s.store_id,
                "sku": s.sku,
                "date": day,
                "received": received,
                "demand": need,
                "sold": need - left,
                "lost": left,
                "waste": waste,
                "end_stock": sum(q for _, q in stock.lots),
                "price": s.price[i],
            }
        )
        # Order at close of today for the delivery tomorrow (or the next one).
        nxt = i + 1
        if nxt in arrival_set:
            j = min(next_after[nxt], nxt + MAX_COVER_DAYS)
            qty = decide(s, nxt, j, stock)
            if qty > 0:
                pending[nxt] = qty
    return pd.DataFrame(rows)


OVERAGE_GRID = (0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)


def tune_overage(
    sales: pd.DataFrame, cfg: ReplayConfig, window_days: int = 60
) -> dict[str, float]:
    """Pick each SKU's overage factor on the ``window_days`` *before* the replay.

    For every factor in the grid the newsvendor policy is replayed on that
    earlier window and the factor with the highest profit wins (profit is
    divided by the list price, so EUR and CHF series are comparable). The
    evaluation window is never seen, so the result is not tuned on its own data.
    """
    tune_cfg = ReplayConfig(
        start=cfg.start - timedelta(days=window_days),
        days=window_days,
        warmup_days=cfg.warmup_days,
        retrain_every_days=cfg.retrain_every_days,
        horizon=cfg.horizon,
        calibration_days=cfg.calibration_days,
        stores=cfg.stores,
        skus=cfg.skus,
    )
    series = _make_series(build_forecasts(sales, tune_cfg), tune_cfg)
    score: dict[str, dict[float, float]] = {}
    for s in series:
        scale = s.cost / COST_SHARE  # list price
        for factor in OVERAGE_GRID:
            s.ratio = critical_ratio(s.cost, s.margin, factor)
            day = simulate_policy(s, "newsvendor")
            day = day[day["date"] >= tune_cfg.start]
            profit = (day["sold"] * (day["price"] - s.cost)).sum() - (
                day["waste"] * s.cost
            ).sum()
            score.setdefault(s.sku, {}).setdefault(factor, 0.0)
            score[s.sku][factor] += float(profit) / scale
    return {sku: max(by.items(), key=lambda kv: kv[1])[0] for sku, by in score.items()}


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Daily rows plus the config and series metadata used for reporting."""

    config: ReplayConfig
    daily: pd.DataFrame
    meta: pd.DataFrame  # store_id, sku, currency, category, cost, margin


def run_replay(sales: pd.DataFrame, cfg: ReplayConfig) -> ReplayResult:
    """Fit walk-forward models and play every policy over every series."""
    forecasts = build_forecasts(sales, cfg)
    series = _make_series(forecasts, cfg)
    frames = [simulate_policy(s, p) for s in series for p in POLICIES]
    daily = pd.concat(frames, ignore_index=True)
    meta = pd.DataFrame(
        [
            {
                "store_id": s.store_id,
                "sku": s.sku,
                "chain": CHAINS.get(s.store_id, ""),
                "currency": s.currency,
                "category": s.product.category,
                "cost": s.cost,
                "margin": s.margin,
            }
            for s in series
        ]
    )
    return ReplayResult(cfg, daily, meta)
