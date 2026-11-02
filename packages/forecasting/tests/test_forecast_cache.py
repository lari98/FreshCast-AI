"""Per-store forecast cache and per-store training mode."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from freshcast.byod import analyze as A
from freshcast.byod.forecast_cache import FORECASTS, ForecastCache, frame_key

SAMPLES = Path(__file__).resolve().parents[3] / "data/samples"


def _two_store_csv(bump_second: int = 0) -> bytes:
    """Sample file plus a second store with different volumes."""
    text = (SAMPLES / "beispiel_absatz.csv").read_bytes().decode("utf-8-sig")
    head, *rows = text.strip().split("\n")
    second = []
    for i, row in enumerate(rows):
        c = row.split(";")
        c[0] = "DE-MUC-002"
        c[4] = str(
            max(0, int(c[4]) * 3 // 4 + (bump_second if i == len(rows) - 1 else 0))
        )
        second.append(";".join(c))
    return "\n".join([head, *rows, *second]).encode("utf-8")


def test_cache_is_lru_expires_and_isolates_copies() -> None:
    cache = ForecastCache(entries=2, ttl_seconds=10)
    frame = pd.DataFrame({"a": [1, 2]})
    cache.put("x", frame, now=0)
    frame.loc[0, "a"] = 99  # changing the original must not change the stored copy
    got = cache.get("x", now=1)
    assert got is not None and got.loc[0, "a"] == 1
    got.loc[0, "a"] = 42  # nor must changing a returned copy
    again = cache.get("x", now=1)
    assert again is not None and again.loc[0, "a"] == 1
    cache.put("y", frame, now=2)
    cache.put("z", frame, now=2)  # evicts x
    assert cache.get("x", now=2) is None
    assert cache.get("y", now=20) is None  # expired
    assert cache.hits == 2 and cache.misses == 2
    off = ForecastCache(entries=0)
    off.put("k", frame)
    assert off.get("k") is None
    cache.clear()
    assert cache.hits == 0


def test_frame_key_reacts_to_values_columns_and_settings() -> None:
    f = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    base = frame_key(f, 1)
    assert base == frame_key(f.copy(), 1)
    assert base != frame_key(f.assign(a=[1.0, 2.5]), 1)
    assert base != frame_key(f.rename(columns={"a": "c"}), 1)
    assert base != frame_key(f, 2)


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    FORECASTS.clear()


def test_per_store_mode_gives_the_same_shape_and_trains_each_store_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fits: list[int] = []
    real = A.DemandForecaster.fit

    def counting(self, df):  # type: ignore[no-untyped-def]
        fits.append(df["store_id"].nunique())
        return real(self, df)

    monkeypatch.setattr(A.DemandForecaster, "fit", counting)
    shared = A.analyze(_two_store_csv(), None, date(2025, 12, 20), per_store=False)
    n_shared = len(fits)
    fits.clear()
    FORECASTS.clear()
    per = A.analyze(_two_store_csv(), None, date(2025, 12, 20), per_store=True)
    assert set(map(str, (i["store_id"] for i in per["items"]))) == {
        "DE-MUC-001",
        "DE-MUC-002",
    }
    assert len(per["items"]) == len(shared["items"])
    assert all(n == 1 for n in fits)  # every model saw exactly one store
    assert (
        len(fits) == 2 * n_shared
    )  # two stores, each with a history and a current model


def test_unchanged_stores_come_from_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    fits: list[int] = []
    real = A.DemandForecaster.fit

    def counting(self, df):  # type: ignore[no-untyped-def]
        fits.append(1)
        return real(self, df)

    monkeypatch.setattr(A.DemandForecaster, "fit", counting)
    as_of = None  # day after the last uploaded day, so the bumped row is history
    first = A.analyze(_two_store_csv(), None, as_of, per_store=True)
    cold = len(fits)
    again = A.analyze(_two_store_csv(), None, as_of, per_store=True)
    assert len(fits) == cold  # nothing retrained
    assert again["items"] == first["items"]
    changed = A.analyze(_two_store_csv(bump_second=9), None, as_of, per_store=True)
    assert len(fits) == cold + cold // 2  # only the changed store was trained again
    assert len(changed["items"]) == len(first["items"])


def test_short_store_falls_back_to_a_shared_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = A._forecast_group
    calls: list[set[str]] = []

    def flaky(known, ahead, cut, start, cal_days):  # type: ignore[no-untyped-def]
        stores = set(known["store_id"].unique())
        calls.append(stores)
        if stores == {"DE-MUC-002"} and calls.count(stores) == 1:
            raise ValueError("too little data")
        return real(known, ahead, cut, start, cal_days)

    monkeypatch.setattr(A, "_forecast_group", flaky)
    out = A.analyze(_two_store_csv(), None, date(2025, 12, 20), per_store=True)
    assert {i["store_id"] for i in out["items"]} == {"DE-MUC-001", "DE-MUC-002"}
    assert {"DE-MUC-002"} in calls and len(calls) >= 3  # retried in the rest group


def test_default_follows_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRESHCAST_PER_STORE", raising=False)
    assert A.per_store_default() is False
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("FRESHCAST_PER_STORE", v)
        assert A.per_store_default() is True
    monkeypatch.setenv("FRESHCAST_PER_STORE", "0")
    assert A.per_store_default() is False
