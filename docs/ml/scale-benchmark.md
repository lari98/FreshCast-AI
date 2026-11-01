# Scale benchmark (synthetic data)

Machine: x86_64 container, 2 vCPU, 7 GB RAM, Python 3.13.18. Last row (50,000 series) reuses the model trained on 20,000 series, to time the daily path at that size.

| Series (store x SKU) | History rows | Feature build | Training | Daily prediction |
|---|---|---|---|---|
| 1,000 | 90,000 | 0.2 s | 4.3 s | 0.03 s |
| 5,000 | 450,000 | 1.1 s | 14.6 s | 0.12 s |
| 20,000 | 1,800,000 | 3.9 s | 78.8 s | 0.36 s |
| 50,000 | 4,500,000 | 8.6 s | reused model | 0.82 s |

Reading: one global model serves all series, so training cost grows roughly linearly with rows and is paid weekly or less, while the daily path (features + prediction) is what runs every day. These are single-machine, synthetic-data numbers, not a production guarantee.

## What this means for a supermarket
- A chain with 1,000 stores x 3,000 fresh lines is 3 million series. The daily path is dominated by prediction, which is embarrassingly parallel by store, so it shards across workers (one Lambda or batch job per store group). Only changed store/SKU pairs need recomputing (see `docs/architecture/events.md`).
- Training is the heavy step but runs weekly or less. A linear extrapolation from the 20,000-series run (79 s on 2 vCPUs) gives roughly 200 s for 50,000 series; this is an extrapolation, not a measurement.
- Not measured here: memory at millions of series (needs partitioning by store), intermittent-demand methods for slow sellers, and cold-start handling for new products. These are the next steps, not claims.
