"""Write German-format example upload files from the synthetic dataset.

Output (data/samples/): beispiel_absatz.csv and beispiel_bestand.csv, written the
way German Excel exports look: ``;`` separator, ``dd.mm.yyyy`` dates, German
headers and decimal commas. Use them to try the upload in the dashboard.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STORE = "DE-MUC-001"


def main() -> None:
    """Create the two sample files."""
    sales = pd.read_csv(ROOT / "data/synthetic/sales.csv", parse_dates=["business_date"])
    products = pd.read_csv(ROOT / "data/synthetic/products.csv")
    last = sales["business_date"].max()
    s = sales[(sales["store_id"] == STORE) & (sales["is_open"].astype(bool))]
    s = s[s["business_date"] > last - pd.Timedelta(days=240)]
    s = s.merge(
        products[["sku", "name_de", "shelf_life_days", "pack_size"]], on="sku"
    )
    out = pd.DataFrame(
        {
            "Filiale": s["store_id"],
            "Artikelnummer": s["sku"],
            "Artikelname": s["name_de"],
            "Datum": s["business_date"].dt.strftime("%d.%m.%Y"),
            "Menge": s["units_sold"],
            "Preis": s["unit_price"].map(lambda v: f"{v:.2f}".replace(".", ",")),
            "Haltbarkeit_Tage": s["shelf_life_days"],
            "Gebindegroesse": s["pack_size"],
        }
    )
    dest = ROOT / "data/samples"
    dest.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest / "beispiel_absatz.csv", sep=";", index=False, encoding="utf-8-sig")
    day = last + timedelta(days=1)
    stock = pd.DataFrame(
        {
            "Filiale": STORE,
            "Artikelnummer": products["sku"],
            "Charge": [f"{sku[:3]}-A" for sku in products["sku"]],
            "Bestand": [(i + 2) * 6 for i in range(len(products))],
            "MHD": [
                (day + timedelta(days=min(2, int(d)))).strftime("%d.%m.%Y")
                for d in products["shelf_life_days"]
            ],
        }
    )
    stock.to_csv(dest / "beispiel_bestand.csv", sep=";", index=False, encoding="utf-8-sig")
    print(f"wrote {len(out)} sales rows and {len(stock)} stock lots to {dest}")  # noqa: T201


if __name__ == "__main__":
    main()
