"""Generate a large, realistic example dataset for the upload feature.

Writes to data/samples/large/ (git-ignored, several MB):
  absatz_gross.csv     ~190,000 sales rows: 3 stores x 100 fresh products x 2 years
  bestand_gross.csv    one stock lot per series, valid on the forecast day
  zukunft_wahrheit.csv the real sales of the next 14 days, so you can compare
                       the forecast with what "actually" happened

The data is SYNTHETIC but has the structure real exports have: category
seasonality, weekday pattern, holidays and Sundays closed, promotions, store
size, a slow trend, random stock-outs (zero sales on open days), a few
duplicate rows, missing days and returns (negative quantities). Format: German
Excel (``;`` separator, ``dd.mm.yyyy``, decimal comma, UTF-8 with BOM).

Usage (repo root): python scripts/make_large_upload.py [--seed 11]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from freshcast.data.calendar import is_store_open
from freshcast.domain.entities import Country

ROOT = Path(__file__).resolve().parents[1]
START, LAST = date(2024, 1, 1), date(2025, 12, 31)
FUTURE_DAYS = 14
STORES = {
    "DE-MUC-001": ("DE", 1.0),
    "AT-VIE-001": ("AT", 0.8),
    "CH-ZRH-001": ("CH", 0.7),
}

# category -> (shelf life days, pack size, price EUR, base daily demand, peak month, names)
CATEGORIES: dict[str, tuple[int, int, float, float, int, list[str]]] = {
    "Obst": (
        5,
        12,
        2.99,
        35,
        7,
        [
            "Erdbeeren",
            "Himbeeren",
            "Heidelbeeren",
            "Äpfel Gala",
            "Birnen",
            "Bananen",
            "Trauben weiß",
            "Orangen",
            "Kirschen",
            "Pfirsiche",
            "Nektarinen",
            "Melone",
            "Mandarinen",
            "Kiwi",
            "Zwetschgen",
        ],
    ),
    "Gemüse": (
        6,
        10,
        1.79,
        40,
        7,
        [
            "Tomaten",
            "Gurken",
            "Paprika rot",
            "Zucchini",
            "Blattsalat",
            "Rucola",
            "Karotten",
            "Brokkoli",
            "Blumenkohl",
            "Spinat",
            "Champignons",
            "Radieschen",
            "Fenchel",
            "Lauch",
            "Spargel grün",
        ],
    ),
    "Molkerei": (
        14,
        6,
        1.49,
        60,
        1,
        [
            "Frischmilch 1 l",
            "Joghurt natur",
            "Joghurt Erdbeer",
            "Quark 500 g",
            "Butter 250 g",
            "Sahne 200 ml",
            "Frischkäse",
            "Mozzarella",
            "Skyr",
            "Kefir",
            "Schmand",
            "Buttermilch",
            "Gouda Scheiben",
            "Camembert",
            "Eier 10er",
        ],
    ),
    "Fleisch": (
        4,
        6,
        5.49,
        25,
        6,
        [
            "Hähnchenbrust",
            "Hackfleisch gemischt",
            "Schweineschnitzel",
            "Rinderhack",
            "Bratwurst",
            "Putenbrust",
            "Schweinenacken",
            "Hähnchenschenkel",
            "Leberkäse",
            "Aufschnitt Schinken",
            "Salami",
            "Gulasch",
            "Rindersteak",
            "Kassler",
            "Wiener",
        ],
    ),
    "Backwaren": (
        3,
        10,
        1.19,
        80,
        12,
        [
            "Weizenbrot",
            "Roggenbrot",
            "Brötchen 6er",
            "Laugenbrezel",
            "Croissant",
            "Vollkornbrot",
            "Baguette",
            "Toastbrot",
            "Dinkelbrot",
            "Mehrkornbrötchen",
            "Berliner",
            "Butterkuchen",
            "Apfeltasche",
            "Käsestange",
            "Zopf",
        ],
    ),
    "Fisch": (
        3,
        4,
        6.99,
        14,
        12,
        [
            "Lachsfilet",
            "Forelle",
            "Garnelen",
            "Thunfisch Steak",
            "Seelachs",
            "Kabeljau",
            "Räucherlachs",
            "Matjes",
            "Dorade",
            "Scholle",
        ],
    ),
    "Fertiggerichte": (
        6,
        8,
        3.49,
        22,
        1,
        [
            "Lasagne",
            "Gemüsesuppe",
            "Kartoffelsalat",
            "Nudelsalat",
            "Tortellini frisch",
            "Maultaschen",
            "Hühnersuppe",
            "Pizza frisch",
            "Wrap Hähnchen",
            "Sushi Box",
            "Linseneintopf",
            "Gulaschsuppe",
            "Quiche",
            "Frühlingsrollen",
            "Chili con Carne",
        ],
    ),
}


def build_products() -> pd.DataFrame:
    """Return ~100 products with per-product jitter, deterministic by index."""
    rng = np.random.default_rng(5)
    rows = []
    for cat, (shelf, pack, price, base, peak, names) in CATEGORIES.items():
        for i, name in enumerate(names):
            rows.append(
                {
                    "sku": f"{cat[:3].upper()}-{i + 1:03d}",
                    "name": name,
                    "category": cat,
                    "shelf_life_days": max(2, shelf + int(rng.integers(-1, 3))),
                    "pack_size": pack,
                    "price": round(price * rng.uniform(0.6, 1.8), 2),
                    "base": base * rng.lognormal(0, 0.45),
                    "peak_month": peak,
                    "seasonal_amp": rng.uniform(0.1, 0.5),
                }
            )
    return pd.DataFrame(rows)


def simulate(seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate daily sales for every store/product; return (sales, products)."""
    rng = np.random.default_rng(seed)
    products = build_products()
    days = pd.date_range(START, LAST + timedelta(days=FUTURE_DAYS), freq="D")
    dow = np.array([0.95, 0.95, 1.0, 1.05, 1.2, 1.45, 0.0])[days.day_of_week]
    month = days.month.to_numpy()
    frames = []
    for store, (country, size) in STORES.items():
        open_day = np.array([is_store_open(Country(country), d.date()) for d in days])
        for p in products.itertuples():
            phase = np.cos(2 * np.pi * (month - p.peak_month) / 12)
            season = 1 + p.seasonal_amp * phase
            trend = 1 + 0.08 * np.arange(len(days)) / 365
            promo = rng.random(len(days)) < 0.04
            lam = p.base * size * dow * season * trend * np.where(promo, 1.5, 1.0)
            # Negative-binomial noise: more realistic spread than Poisson.
            r = 12.0
            units = rng.negative_binomial(r, r / (r + lam + 1e-9)).astype(int)
            stockout = rng.random(len(days)) < 0.008
            units = np.where(stockout, 0, units)
            frames.append(
                pd.DataFrame(
                    {
                        "store_id": store,
                        "sku": p.sku,
                        "business_date": days,
                        "units_sold": units,
                        "open": open_day,
                    }
                )
            )
    sales = pd.concat(frames, ignore_index=True)
    return sales[sales["open"]].drop(columns="open"), products


def _de_date(s: pd.Series) -> pd.Series:
    return s.dt.strftime("%d.%m.%Y")


def main() -> None:
    """Write the three files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    sales, products = simulate(args.seed)
    rng = np.random.default_rng(args.seed + 1)
    cutoff = pd.Timestamp(LAST)
    hist = sales[sales["business_date"] <= cutoff].copy()
    truth = sales[sales["business_date"] > cutoff].copy()

    # Real-world mess, small amounts: missing days, duplicates, returns.
    hist = hist.drop(hist.sample(frac=0.004, random_state=args.seed).index)
    dup = hist.sample(frac=0.002, random_state=args.seed + 2)
    ret = hist.sample(40, random_state=args.seed + 3).assign(units_sold=-1)
    hist = pd.concat([hist, dup, ret]).sort_values(["business_date", "store_id", "sku"])

    meta = products.set_index("sku")
    out = pd.DataFrame(
        {
            "Filiale": hist["store_id"],
            "Artikelnummer": hist["sku"],
            "Artikelname": hist["sku"].map(meta["name"]),
            "Datum": _de_date(hist["business_date"]),
            "Menge": hist["units_sold"],
            "Preis": hist["sku"]
            .map(meta["price"])
            .map(lambda v: f"{v:.2f}".replace(".", ",")),
            "Haltbarkeit_Tage": hist["sku"].map(meta["shelf_life_days"]),
            "Gebindegroesse": hist["sku"].map(meta["pack_size"]),
        }
    )
    dest = ROOT / "data/samples/large"
    dest.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest / "absatz_gross.csv", sep=";", index=False, encoding="utf-8-sig")

    series = hist[["store_id", "sku"]].drop_duplicates()
    next_day = LAST + timedelta(days=1)
    stock = pd.DataFrame(
        {
            "Filiale": series["store_id"].to_numpy(),
            "Artikelnummer": series["sku"].to_numpy(),
            "Charge": [f"{s[:7]}-A" for s in series["sku"]],
            "Bestand": (
                meta.loc[series["sku"], "base"].to_numpy()
                * rng.uniform(0.3, 1.2, len(series))
            )
            .round()
            .astype(int)
            + 1,
            "MHD": [
                (next_day + timedelta(days=int(rng.integers(0, 4)))).strftime(
                    "%d.%m.%Y"
                )
                for _ in range(len(series))
            ],
        }
    )
    stock.to_csv(dest / "bestand_gross.csv", sep=";", index=False, encoding="utf-8-sig")

    t = truth.assign(Datum=_de_date(truth["business_date"]))
    t[["store_id", "sku", "Datum", "units_sold"]].rename(
        columns={"store_id": "Filiale", "sku": "Artikelnummer", "units_sold": "Menge"}
    ).to_csv(dest / "zukunft_wahrheit.csv", sep=";", index=False, encoding="utf-8-sig")
    size = (dest / "absatz_gross.csv").stat().st_size / 2**20
    print(
        f"{len(out):,} sales rows ({size:.1f} MB), {len(series)} series, {len(stock)} lots"
    )


if __name__ == "__main__":
    main()
