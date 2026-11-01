"""Forecast and order proposals for user-supplied data.

Pipeline: validated daily panel -> leakage-safe features -> two models:

* a *history* model trained before the last 14 days, so the chart's recent
  actual-vs-forecast comparison is out-of-sample and honest;
* a *current* model trained on everything, used for the next 7 days.

Then, per store/SKU, the FEFO planner proposes an order from the current stock
lots. Cost assumptions (unit cost 60 % and margin 40 % of price) are stated in
the output; the model never decides on its own, a person approves.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from freshcast.assistant.facts import ExplanationFacts
from freshcast.assistant.templates import render_template
from freshcast.byod.ingest import (
    IngestError,
    QualityReport,
    _country,
    clean_sales,
    clean_stock,
    read_csv_bytes,
)
from freshcast.data.calendar import is_holiday, is_store_open
from freshcast.features.builder import build_features
from freshcast.models.lgbm import DemandForecaster
from freshcast.replenishment.engine import (
    ReplenishmentRequest,
    StockLot,
    calculate_replenishment,
)
from freshcast.replenishment.planner import DemandScenarios, PlanningRequest, plan_order

HORIZON = 2
HISTORY_DAYS = 14
FUTURE_DAYS = 7
CALIBRATION_MIN_SPAN = 120  # days of history needed to hold out 28 for calibration
DEFAULT_SHELF_LIFE = 5
COST_SHARE, MARGIN_SHARE = 0.6, 0.4
LANGS = ("de", "en")


def _future_rows(panel: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Rows for the days to forecast: calendar known, demand unknown (NaN)."""
    rows = []
    for (store, sku), g in panel.groupby(["store_id", "sku"]):
        country = _country(str(store))
        price = (
            g["unit_price"].dropna().iloc[-1]
            if "unit_price" in g and g["unit_price"].notna().any()
            else 1.0
        )
        for k in range(FUTURE_DAYS):
            d = as_of + timedelta(days=k)
            rows.append(
                {
                    "store_id": store,
                    "sku": sku,
                    "business_date": pd.Timestamp(d),
                    "units_sold": np.nan,
                    "is_open": is_store_open(country, d),
                    "is_holiday": is_holiday(country, d),
                    "unit_price": price,
                }
            )
    return pd.DataFrame(rows)


def _risk(days_left: int, shelf_life: int) -> str:
    if days_left <= 1:
        return "high"
    return "medium" if days_left <= max(2, shelf_life // 2) else "low"


def _num(value: Any, default: float) -> float:
    return default if value is None or pd.isna(value) else float(value)


def analyze(
    sales_csv: bytes, stock_csv: bytes | None = None, as_of: date | None = None
) -> dict[str, Any]:
    """Return a dashboard payload for the uploaded files (raises IngestError)."""
    panel, report, as_of_date = clean_sales(read_csv_bytes(sales_csv, "sales"), as_of)

    stock = pd.DataFrame()
    if stock_csv is not None:
        stock, stock_warnings = clean_stock(
            read_csv_bytes(stock_csv, "stock"), as_of_date
        )
        report.warnings += stock_warnings
    else:
        report.warnings.append(
            "no stock file: shelves are assumed empty, so proposed quantities are "
            "too high for stores that hold stock"
        )

    for col in (
        "unit_price",
        "product_name",
        "category",
        "chain",
        "shelf_life_days",
        "pack_size",
    ):
        if col not in panel:
            panel[col] = (
                np.nan if col not in ("product_name", "category", "chain") else None
            )
    price = panel["unit_price"].fillna(1.0)
    panel["unit_price"] = price
    future = _future_rows(panel, as_of_date)
    base = panel[
        ["store_id", "sku", "business_date", "units_sold", "is_open", "is_holiday"]
    ]
    for flag, val in (("is_promo", 0), ("unit_price", 1.0)):
        base = base.assign(**{flag: val})
    base["unit_price"] = panel["unit_price"].to_numpy()
    full = pd.concat([base, future.assign(is_promo=0)], ignore_index=True)
    feats = build_features(full, HORIZON)

    span = (pd.Timestamp(as_of_date) - feats["business_date"].min()).days
    cal_days = 28 if span >= CALIBRATION_MIN_SPAN else 0
    report.calibrated = cal_days > 0
    if not report.calibrated:
        report.warnings.append(
            f"less than {CALIBRATION_MIN_SPAN} days of history: intervals are not "
            "calibrated and are probably too narrow"
        )
    known = feats[feats["business_date"] < pd.Timestamp(as_of_date)]
    cut = pd.Timestamp(as_of_date - timedelta(days=HISTORY_DAYS + HORIZON))
    try:
        hist_model = DemandForecaster(calibration_days=cal_days, n_jobs=2).fit(
            known[known["business_date"] < cut]
        )
        now_model = DemandForecaster(calibration_days=cal_days, n_jobs=2).fit(known)
    except ValueError as exc:
        raise IngestError([f"history too short to train a model: {exc}"]) from exc

    hist = known[
        known["business_date"]
        >= pd.Timestamp(as_of_date - timedelta(days=HISTORY_DAYS))
    ].copy()
    hist[["point", "lower", "upper"]] = hist_model.predict(hist)
    ahead = feats[feats["business_date"] >= pd.Timestamp(as_of_date)].copy()
    ahead[["point", "lower", "upper"]] = now_model.predict(ahead)
    window = pd.concat([hist, ahead]).sort_values("business_date")

    items = [
        _item(store, sku, window, panel, stock, as_of_date)
        for (store, sku) in sorted(
            {(s, k) for s, k in zip(panel["store_id"], panel["sku"], strict=True)}
        )
    ]
    return {
        "disclaimer": (
            "Forecast from your uploaded data. Assumptions: unit cost 60 % and "
            "margin 40 % of price, 1-day supplier lead time, delivery Monday to "
            "Saturday. A person must approve every order."
        ),
        "source": "upload",
        "as_of": as_of_date.isoformat(),
        "horizon_days": HORIZON,
        "items": items,
        "quality": report.to_dict(),
    }


def _item(
    store: str,
    sku: str,
    window: pd.DataFrame,
    panel: pd.DataFrame,
    stock: pd.DataFrame,
    as_of: date,
) -> dict[str, Any]:
    rows = window[(window["store_id"] == store) & (window["sku"] == sku)]
    meta = panel[(panel["store_id"] == store) & (panel["sku"] == sku)].iloc[-1]
    name = str(meta["product_name"]) if pd.notna(meta["product_name"]) else sku
    shelf = int(_num(meta["shelf_life_days"], DEFAULT_SHELF_LIFE))
    pack = max(1, int(_num(meta["pack_size"], 1)))
    unit_price = _num(meta["unit_price"], 1.0)
    currency = "CHF" if store[:2].upper() == "CH" else "EUR"

    records: list[dict[Any, Any]] = rows.to_dict("records")
    series = [
        {
            "date": r["business_date"].date().isoformat(),
            "actual": int(r["units_sold"])
            if r["business_date"].date() < as_of
            else None,
            "lower": round(float(r["lower"]), 1),
            "point": round(float(r["point"]), 1),
            "upper": round(float(r["upper"]), 1),
            "is_open": bool(r["is_open"]),
        }
        for r in records
    ]
    future = rows[rows["business_date"] >= pd.Timestamp(as_of)]
    scen = DemandScenarios.from_floats(
        future["lower"].tolist(), future["point"].tolist(), future["upper"].tolist()
    )
    mine = (
        stock[(stock["store_id"] == store) & (stock["sku"] == sku)]
        if not stock.empty
        else stock
    )
    stock_rows: list[dict[Any, Any]] = mine.to_dict("records")
    lots = tuple(
        StockLot(
            str(r["lot_id"]) or f"{sku[:3]}-{i + 1:02d}",
            int(r["quantity"]),
            r["use_by_date"].date(),
        )
        for i, r in enumerate(stock_rows)
    )
    plan = plan_order(
        PlanningRequest(
            store_id=store,
            sku=sku,
            as_of_date=as_of,
            scenarios=scen,
            stock_lots=lots,
            deliveries=(),
            supplier_lead_days=1,
            delivery_weekdays=frozenset(range(6)),
            order_multiple=pack,
            remaining_shelf_life_days=max(1, shelf - 1),
            unit_cost=unit_price * COST_SHARE,
            unit_margin=unit_price * MARGIN_SHARE,
        )
    )
    request = ReplenishmentRequest(
        store,
        sku,
        as_of,
        sum(scen.point),
        max(0, sum(scen.upper) - sum(scen.point)),
        0,
        1,
        pack,
        lots,
    )
    decision = calculate_replenishment(request)
    facts = {
        lang: dataclasses.replace(
            ExplanationFacts.from_replenishment(request, decision, name),
            recommended_order_units=plan.recommended_order_units,
            arrival_date=plan.arrival_date,
        )
        for lang in LANGS
    }
    outlook = plan.outcomes["point"]
    return {
        "store_id": store,
        "city": store,
        "chain": str(meta["chain"]) if pd.notna(meta["chain"]) else "",
        "currency": currency,
        "sku": sku,
        "name": {"de": name, "en": name},
        "shelf_life_days": shelf,
        "unit_price": round(unit_price, 2),
        "category": str(meta["category"]) if pd.notna(meta["category"]) else "",
        "series": series,
        "lots": [
            {
                "lot_id": lot.lot_id,
                "quantity": lot.quantity,
                "use_by": lot.use_by_date.isoformat(),
                "days_left": (lot.use_by_date - as_of).days,
                "risk": _risk((lot.use_by_date - as_of).days, shelf),
            }
            for lot in lots
        ],
        "proposal": {
            "recommended_order_units": plan.recommended_order_units,
            "usable_stock_units": decision.usable_stock_units,
            "expiring_stock_units": decision.expiring_stock_units,
            "target_stock_units": decision.target_stock_units,
            "order_multiple": pack,
            "arrival_date": plan.arrival_date.isoformat(),
            "forecast_units": request.forecast_units,
            "safety_stock_units": request.safety_stock_units,
            "outlook_waste_units": outlook.waste_units,
            "outlook_lost_units": outlook.lost_units,
        },
        "explanation": {
            "de": render_template(facts["de"], "de"),
            "en": render_template(facts["en"], "en"),
        },
    }


__all__ = ["QualityReport", "analyze"]
