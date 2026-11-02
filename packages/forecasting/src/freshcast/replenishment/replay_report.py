"""Reporting for the policy replay: summaries, segments, JSON and Markdown.

Kept apart from ``replay.py`` (which only simulates) so each file has one job.
Command line: ``python -m freshcast.replenishment.replay_report``.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from freshcast.replenishment.newsvendor import critical_ratio
from freshcast.replenishment.replay import (
    COST_SHARE,
    POLICIES,
    ReplayConfig,
    ReplayResult,
    run_replay,
    tune_overage,
)


def _counted(result: ReplayResult) -> pd.DataFrame:
    """Join meta and drop the warm-up days; add value columns."""
    cfg = result.config
    df = result.daily.merge(result.meta, on=["store_id", "sku"])
    df = df[df["date"] >= cfg.start].copy()
    df["revenue"] = df["sold"] * df["price"]
    df["purchases"] = df["received"] * df["cost"]
    df["waste_cost"] = df["waste"] * df["cost"]
    df["lost_margin"] = df["lost"] * (df["price"] - df["cost"]).clip(lower=0)
    # Revenue minus the cost of what was sold or wasted; leftover stays at cost.
    df["profit"] = df["revenue"] - df["sold"] * df["cost"] - df["waste_cost"]
    return df


def summarise(result: ReplayResult) -> pd.DataFrame:
    """One row per policy and currency with the headline metrics."""
    df = _counted(result)
    agg = df.groupby(["policy", "currency"], as_index=False).agg(
        received=("received", "sum"),
        demand=("demand", "sum"),
        sold=("sold", "sum"),
        lost=("lost", "sum"),
        waste=("waste", "sum"),
        revenue=("revenue", "sum"),
        waste_cost=("waste_cost", "sum"),
        lost_margin=("lost_margin", "sum"),
        profit=("profit", "sum"),
    )
    agg["fill_rate"] = agg["sold"] / agg["demand"].where(agg["demand"] > 0)
    agg["waste_rate"] = agg["waste"] / agg["received"].where(agg["received"] > 0)
    order = {p: i for i, p in enumerate(POLICIES)}
    return agg.sort_values(
        ["currency", "policy"], key=lambda c: c.map(order) if c.name == "policy" else c
    ).reset_index(drop=True)


def segments(result: ReplayResult) -> list[dict[str, Any]]:
    """Raw sums per market, chain and policy, so a UI can filter and re-aggregate.

    Ratios are not stored: they must be recomputed from sums after filtering.
    """
    df = _counted(result)
    df["market"] = df["store_id"].str.split("-").str[0]
    g = df.groupby(["market", "chain", "currency", "policy"], as_index=False).agg(
        received=("received", "sum"),
        demand=("demand", "sum"),
        sold=("sold", "sum"),
        lost=("lost", "sum"),
        waste=("waste", "sum"),
        revenue=("revenue", "sum"),
        waste_cost=("waste_cost", "sum"),
        lost_margin=("lost_margin", "sum"),
        profit=("profit", "sum"),
    )
    out: list[dict[str, Any]] = []
    for (market, chain, currency), sub in g.groupby(["market", "chain", "currency"]):
        policies = {
            str(r["policy"]): {
                k: round(float(r[k]), 2)
                for k in (
                    "received",
                    "demand",
                    "sold",
                    "lost",
                    "waste",
                    "revenue",
                    "waste_cost",
                    "lost_margin",
                    "profit",
                )
            }
            for r in sub.to_dict("records")
        }
        out.append(
            {
                "market": str(market),
                "chain": str(chain),
                "currency": str(currency),
                "policies": policies,
            }
        )
    return out


def weekly_units(result: ReplayResult) -> pd.DataFrame:
    """Waste and lost units per policy and week (units, so currency-free)."""
    df = _counted(result)
    start = pd.Timestamp(result.config.start)
    df["week"] = ((pd.to_datetime(df["date"]) - start).dt.days // 7).astype(int)
    return df.groupby(["policy", "week"], as_index=False)[["waste", "lost"]].sum()


def weekly_wins(result: ReplayResult, a: str, b: str) -> tuple[int, int]:
    """Count weeks in which policy ``a`` earned more profit than ``b``.

    Profit is divided by the list price so EUR and CHF series add up fairly.
    """
    df = _counted(result)
    df["profit_idx"] = df["profit"] / (df["cost"] / COST_SHARE)
    start = pd.Timestamp(result.config.start)
    df["week"] = ((pd.to_datetime(df["date"]) - start).dt.days // 7).astype(int)
    w = df.groupby(["week", "policy"])["profit_idx"].sum().unstack("policy").dropna()
    return int((w[a] > w[b]).sum()), int(len(w))


def by_category(result: ReplayResult) -> pd.DataFrame:
    """Waste rate and fill rate per policy and product group."""
    df = _counted(result)
    g = df.groupby(["policy", "category"], as_index=False).agg(
        received=("received", "sum"),
        waste=("waste", "sum"),
        demand=("demand", "sum"),
        sold=("sold", "sum"),
    )
    g["waste_rate"] = g["waste"] / g["received"].where(g["received"] > 0)
    g["fill_rate"] = g["sold"] / g["demand"].where(g["demand"] > 0)
    return g


def _pct(a: float, b: float) -> float | None:
    return None if b == 0 else a / b - 1.0


def to_json(result: ReplayResult) -> dict[str, Any]:
    """Compact payload for the dashboard's Savings tab."""
    s = summarise(result)
    cfg = result.config
    policies: dict[str, Any] = {}
    for policy in POLICIES:
        per_cur: dict[str, Any] = {}
        for row in s[s["policy"] == policy].to_dict("records"):
            base = s[(s["policy"] == "naive") & (s["currency"] == row["currency"])]
            b = base.iloc[0].to_dict()
            per_cur[str(row["currency"])] = {
                "revenue": round(float(row["revenue"]), 2),
                "profit": round(float(row["profit"]), 2),
                "waste_cost": round(float(row["waste_cost"]), 2),
                "lost_margin": round(float(row["lost_margin"]), 2),
                "waste_units": int(row["waste"]),
                "lost_units": int(row["lost"]),
                "fill_rate": round(float(row["fill_rate"]), 4),
                "waste_rate": round(float(row["waste_rate"]), 4),
                "profit_vs_naive": _pct(float(row["profit"]), float(b["profit"])),
                "waste_cost_vs_naive": _pct(
                    float(row["waste_cost"]), float(b["waste_cost"])
                ),
            }
        policies[policy] = per_cur
    wk = weekly_units(result)
    weekly = {
        p: {
            "waste": wk[wk["policy"] == p].sort_values("week")["waste"].tolist(),
            "lost": wk[wk["policy"] == p].sort_values("week")["lost"].tolist(),
        }
        for p in POLICIES
    }
    cat = by_category(result)
    categories = {
        c: {
            p: {
                "waste_rate": round(float(r["waste_rate"]), 4),
                "fill_rate": round(float(r["fill_rate"]), 4),
            }
            for p in POLICIES
            for r in cat[(cat["category"] == c) & (cat["policy"] == p)].to_dict(
                "records"
            )
        }
        for c in sorted(cat["category"].unique())
    }
    wins, weeks = weekly_wins(result, "newsvendor", "rule_v1")
    return {
        "newsvendor_beats_rule_v1_weeks": {"wins": wins, "weeks": weeks},
        "overage_factors": cfg.overage_factors,
        "disclaimer": (
            "Synthetic data and assumed costs (60% cost, 40% margin). "
            "Mechanics demo, not evidence of real savings."
        ),
        "from": cfg.start.isoformat(),
        "to": (cfg.start + timedelta(days=cfg.days - 1)).isoformat(),
        "series": int(len(result.meta)),
        "policies": policies,
        "segments": segments(result),
        "weekly": weekly,
        "categories": categories,
    }


def render_markdown(result: ReplayResult) -> str:
    """Markdown report for docs/ml/policy-replay.md."""
    cfg = result.config
    s = summarise(result)
    end = cfg.start + timedelta(days=cfg.days - 1)
    lines = [
        "# Policy replay (synthetic data)",
        "",
        f"Window: {cfg.start} to {end} ({cfg.days} days, {len(result.meta)} "
        f"store/SKU series), after a {cfg.warmup_days}-day warm-up. Models are "
        f"refitted every {cfg.retrain_every_days} days on earlier data only. "
        "Assumed costs: purchase cost 60 %, margin 40 % of the list price.",
        "",
    ]
    for cur in sorted(s["currency"].unique()):
        sub = s[s["currency"] == cur]
        base = sub[sub["policy"] == "naive"].iloc[0]
        lines += [
            f"## {cur}",
            "",
            "| Policy | Fill rate | Waste rate | Waste cost | Lost margin "
            "| Profit | Profit vs naive |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in sub.to_dict("records"):
            delta = _pct(float(r["profit"]), float(base["profit"]))
            shown = "-" if delta is None or r["policy"] == "naive" else f"{delta:+.1%}"
            lines.append(
                f"| {r['policy']} | {r['fill_rate']:.1%} | {r['waste_rate']:.1%} "
                f"| {r['waste_cost']:,.0f} | {r['lost_margin']:,.0f} "
                f"| {r['profit']:,.0f} | {shown} |"
            )
        lines.append("")
    wins, weeks = weekly_wins(result, "newsvendor", "rule_v1")
    lines += [
        "## Paired weekly check",
        "",
        f"The newsvendor policy earned more profit than the v1 rule in {wins} of "
        f"{weeks} weeks. A small overall gain with few winning weeks would be "
        "noise; read the profit column together with this line.",
        "",
    ]
    if cfg.overage_factors:
        lines += [
            "## Tuned overage factors",
            "",
            "Share of a leftover unit's cost that is really lost. Chosen per SKU "
            "from a grid on the 60 days *before* the window (never on the "
            "evaluated days). 0.05 is the lowest value in the grid.",
            "",
            "| SKU | Overage factor | Critical ratio (cost 60 %, margin 40 %) |",
            "|---|---|---|",
        ]
        for sku, f in sorted(cfg.overage_factors.items()):
            lines.append(f"| {sku} | {f:.2f} | {critical_ratio(0.6, 0.4, f):.2f} |")
        lines.append("")
    lines += [
        "## How to read this",
        "",
        "* Recorded sales stand in for demand (no censoring) and the data is "
        "simulated, so this shows how the policies behave, not what a real "
        "store would save.",
        "* With a plain single-period newsvendor (overage factor 1.0) the target "
        "falls below expected demand and loses to the v1 rule, because leftovers "
        "are mostly sold the next day. Estimating the carry-over per SKU fixes "
        "that; see ADR 0004.",
        "* A policy that wins here still needs a real pilot before any claim.",
        "",
    ]
    return "\n".join(lines)


def cfg_fields(cfg: ReplayConfig) -> dict[str, Any]:
    """Shallow field dict of a config (for building a modified copy)."""
    return {f: getattr(cfg, f) for f in cfg.__dataclass_fields__}


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Replay ordering policies")
    parser.add_argument("--data", type=Path, default=Path("data/synthetic/sales.csv"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 10, 1))
    parser.add_argument("--days", type=int, default=92)
    parser.add_argument("--out", type=Path, default=Path("docs/ml/policy-replay.md"))
    parser.add_argument(
        "--json", type=Path, default=Path("apps/dashboard/public/demo/replay.json")
    )
    parser.add_argument("--no-tune", action="store_true", help="overage factor 1.0")
    args = parser.parse_args()
    sales = pd.read_csv(args.data, parse_dates=["business_date"])
    cfg = ReplayConfig(start=args.start, days=args.days)
    factors = {} if args.no_tune else tune_overage(sales, cfg)
    result = run_replay(
        sales, ReplayConfig(**{**cfg_fields(cfg), "overage_factors": factors})
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(result), encoding="utf-8")
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(to_json(result), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"wrote {args.out} and {args.json}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
