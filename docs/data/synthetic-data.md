# Synthetic data

All data is invented (no real stores, customers or companies) and is
reproducible: `python -m freshcast.data.synthetic --start 2025-01-01 --days 365 --seed 42 --out data/synthetic`.

| File | Content |
|---|---|
| stores.csv | 7 stores in DE, AT and CH (EUR / CHF) |
| products.csv | 8 perishable SKUs with shelf life and pack size |
| sales.csv | Daily units, price, open/holiday/promo flags per store and SKU |

Modelling assumptions: stores closed on Sundays and nationwide holidays;
weekday and annual seasonality (strawberries peak in June); promotions with
20 % discount and 35 % uplift; Swiss prices 15 % above EUR base (illustrative).
Regional holidays are not modelled. Not suitable for estimating real-world performance.
