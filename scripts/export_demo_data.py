"""Export demo data for the dashboard from the real model on synthetic data.

Usage (repo root): python scripts/export_demo_data.py
Writes apps/dashboard/public/demo/data.json. Everything is synthetic; the
dashboard labels it as a demo. Stock lots are invented deterministically.
"""

from __future__ import annotations

import dataclasses
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from freshcast.assistant.facts import ExplanationFacts
from freshcast.assistant.templates import render_template
from freshcast.data.synthetic import PRODUCTS, STORES
from freshcast.features.builder import build_features
from freshcast.models.lgbm import DemandForecaster
from freshcast.replenishment.engine import (
    ReplenishmentRequest,
    StockLot,
    calculate_replenishment,
)
from freshcast.replenishment.planner import (
    DemandScenarios,
    PlanningRequest,
    plan_order,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2025, 12, 22)  # Monday; the model never saw data after AS_OF - 14
HISTORY_DAYS = 14
HORIZON = 2
DEMO_STORES = ("DE-MUC-001", "AT-VIE-001", "CH-ZRH-001")
LANGS = ("de", "en")


def _risk(days_left: int, shelf_life: int) -> str:
    if days_left <= 1:
        return "high"
    return "medium" if days_left <= max(2, shelf_life // 2) else "low"


def main() -> None:
    """Train, forecast, plan and write the JSON file."""
    sales = pd.read_csv(
        ROOT / "data/synthetic/sales.csv", parse_dates=["business_date"]
    )
    feats = build_features(sales, HORIZON)
    cut = pd.Timestamp(AS_OF - timedelta(days=HISTORY_DAYS + HORIZON))
    model = DemandForecaster().fit(feats[feats["business_date"] < cut])
    window = feats[
        (feats["business_date"] >= pd.Timestamp(AS_OF - timedelta(days=HISTORY_DAYS)))
        & (feats["business_date"] < pd.Timestamp(AS_OF + timedelta(days=7)))
        & feats["store_id"].isin(DEMO_STORES)
    ].copy()
    window[["point", "lower", "upper"]] = model.predict(window)

    rng = random.Random(7)
    stores = {s.store_id: s for s in STORES}
    items = []
    for store_id in DEMO_STORES:
        for product in PRODUCTS:
            rows = window[
                (window["store_id"] == store_id) & (window["sku"] == product.sku)
            ]
            rows = rows.sort_values("business_date")
            series = [
                {
                    "date": r.business_date.date().isoformat(),
                    "actual": int(r.units_sold)
                    if r.business_date.date() < AS_OF
                    else None,
                    "lower": round(float(r.lower), 1),
                    "point": round(float(r.point), 1),
                    "upper": round(float(r.upper), 1),
                    "is_open": bool(r.is_open),
                }
                for r in rows.itertuples()
            ]
            future = rows[rows["business_date"] >= pd.Timestamp(AS_OF)]
            scen = DemandScenarios.from_floats(
                future["lower"].tolist(),
                future["point"].tolist(),
                future["upper"].tolist(),
            )
            lots = []
            for i in range(rng.randint(2, 3)):
                days_left = rng.randint(0, product.shelf_life_days)
                qty = max(1, round(product.base_daily_demand * rng.uniform(0.4, 1.4)))
                lots.append(
                    StockLot(
                        f"{product.sku[:3]}-{i + 1:02d}",
                        qty,
                        AS_OF + timedelta(days=days_left),
                    )
                )
            plan = plan_order(
                PlanningRequest(
                    store_id=store_id,
                    sku=product.sku,
                    as_of_date=AS_OF,
                    scenarios=scen,
                    stock_lots=tuple(lots),
                    deliveries=(),
                    supplier_lead_days=1,
                    delivery_weekdays=frozenset(range(6)),
                    order_multiple=product.pack_size,
                    remaining_shelf_life_days=max(1, product.shelf_life_days - 1),
                    unit_cost=product.base_price_eur * 0.6,
                    unit_margin=product.base_price_eur * 0.4,
                )
            )
            # Reference numbers (usable/expiring stock, target) from the simple rule.
            request = ReplenishmentRequest(
                store_id,
                product.sku,
                AS_OF,
                sum(scen.point),
                max(0, sum(scen.upper) - sum(scen.point)),
                0,
                1,
                product.pack_size,
                tuple(lots),
            )
            decision = calculate_replenishment(request)
            facts = {
                lang: dataclasses.replace(
                    ExplanationFacts.from_replenishment(
                        request, decision, getattr(product, f"name_{lang}")
                    ),
                    recommended_order_units=plan.recommended_order_units,
                    arrival_date=plan.arrival_date,
                )
                for lang in LANGS
            }
            outlook = plan.outcomes["point"]
            items.append(
                {
                    "store_id": store_id,
                    "city": stores[store_id].city,
                    "currency": stores[store_id].currency.value,
                    "sku": product.sku,
                    "name": {"de": product.name_de, "en": product.name_en},
                    "shelf_life_days": product.shelf_life_days,
                    "unit_price": product.base_price_eur,
                    "category": product.category,
                    "series": series,
                    "lots": [
                        {
                            "lot_id": lot.lot_id,
                            "quantity": lot.quantity,
                            "use_by": lot.use_by_date.isoformat(),
                            "days_left": (lot.use_by_date - AS_OF).days,
                            "risk": _risk(
                                (lot.use_by_date - AS_OF).days, product.shelf_life_days
                            ),
                        }
                        for lot in lots
                    ],
                    "proposal": {
                        "recommended_order_units": plan.recommended_order_units,
                        "usable_stock_units": decision.usable_stock_units,
                        "expiring_stock_units": decision.expiring_stock_units,
                        "target_stock_units": decision.target_stock_units,
                        "order_multiple": product.pack_size,
                        "arrival_date": plan.arrival_date.isoformat(),
                        "forecast_units": request.forecast_units,
                        "safety_stock_units": request.safety_stock_units,
                        "outlook_waste_units": outlook.waste_units,
                        "outlook_lost_units": outlook.lost_units,
                    },
                    "explanation": {
                        lang: render_template(facts[lang], lang) for lang in LANGS
                    },  # type: ignore[arg-type]
                }
            )
    out = {
        "disclaimer": "Synthetic demo data. Not real sales, not a certified product.",
        "as_of": AS_OF.isoformat(),
        "horizon_days": HORIZON,
        "items": items,
    }
    target = ROOT / "apps/dashboard/public/demo/data.json"
    target.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {target} ({target.stat().st_size // 1024} KiB, {len(items)} items)")


if __name__ == "__main__":
    main()
