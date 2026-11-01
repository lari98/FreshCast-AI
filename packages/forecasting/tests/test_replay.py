"""Policy replay: stock conservation, warm-up exclusion and report outputs."""

from dataclasses import asdict
from datetime import date

import pandas as pd
import pytest

from freshcast.data.synthetic import generate_sales
from freshcast.replenishment.replay import (
    OVERAGE_GRID,
    POLICIES,
    ReplayConfig,
    cfg_fields,
    render_markdown,
    run_replay,
    summarise,
    to_json,
    tune_overage,
    weekly_units,
)

SKUS = ("MILK-1L", "BREAD-WHEAT-750G")


@pytest.fixture(scope="module")
def sales() -> pd.DataFrame:
    rows = [asdict(r) for r in generate_sales(date(2025, 1, 1), 230)]
    df = pd.DataFrame(rows)
    df["currency"] = df["currency"].astype(str)
    return df


@pytest.fixture(scope="module")
def cfg() -> ReplayConfig:
    return ReplayConfig(
        start=date(2025, 7, 1),
        days=30,
        retrain_every_days=15,
        stores=("DE-MUC-001",),
        skus=SKUS,
    )


@pytest.fixture(scope="module")
def result(sales: pd.DataFrame, cfg: ReplayConfig):  # type: ignore[no-untyped-def]
    return run_replay(sales, cfg)


def test_every_policy_conserves_stock(result) -> None:  # type: ignore[no-untyped-def]
    """Units received = sold + wasted + still on the shelf, per series and policy."""
    for (_, _, _), g in result.daily.groupby(["policy", "store_id", "sku"]):
        g = g.sort_values("date")
        assert g["received"].sum() == (
            g["sold"].sum() + g["waste"].sum() + g["end_stock"].iloc[-1]
        )
        assert (g["sold"] + g["lost"] == g["demand"]).all()
        assert (g["sold"] <= g["demand"]).all()


def test_all_policies_and_series_present(result) -> None:  # type: ignore[no-untyped-def]
    assert set(result.daily["policy"]) == set(POLICIES)
    assert len(result.meta) == len(SKUS)


def test_warmup_days_are_not_counted(result, cfg: ReplayConfig) -> None:  # type: ignore[no-untyped-def]
    assert result.daily["date"].min() < cfg.start
    s = summarise(result)
    counted = result.daily[result.daily["date"] >= cfg.start]
    assert int(s["demand"].sum()) == int(counted["demand"].sum())


def test_summary_rates_are_valid(result) -> None:  # type: ignore[no-untyped-def]
    s = summarise(result)
    assert s["fill_rate"].between(0, 1).all()
    assert s["waste_rate"].between(0, 1).all()
    assert (s["waste_cost"] >= 0).all()


def test_naive_never_beats_everything_on_fill_rate(result) -> None:  # type: ignore[no-untyped-def]
    s = summarise(result).set_index("policy")
    assert s.loc["rule_v1", "fill_rate"] >= s.loc["naive", "fill_rate"]


def test_json_and_markdown_outputs(result) -> None:  # type: ignore[no-untyped-def]
    payload = to_json(result)
    assert set(payload["policies"]) == set(POLICIES)
    assert payload["newsvendor_beats_rule_v1_weeks"]["weeks"] >= 4
    assert "profit_vs_naive" in payload["policies"]["rule_v1"]["EUR"]
    de = payload["markets"]["DE"]
    assert de["currency"] == "EUR"
    assert set(de["policies"]) == set(POLICIES)
    assert len(weekly_units(result)) > 0
    assert "# Policy replay" in render_markdown(result)


def test_tuning_picks_grid_values_from_earlier_data(
    sales: pd.DataFrame, cfg: ReplayConfig
) -> None:
    factors = tune_overage(sales, cfg, window_days=45)
    assert set(factors) == set(SKUS)
    assert all(f in OVERAGE_GRID for f in factors.values())
    tuned = ReplayConfig(**{**cfg_fields(cfg), "overage_factors": factors})
    assert render_markdown(run_replay(sales, tuned)).count("Overage factor") == 1


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        ReplayConfig(start=date(2025, 1, 1), days=0)
