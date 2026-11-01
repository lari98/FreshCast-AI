# ADR 0004: Profit-optimal ordering and policy replay

Status: accepted (phase 13)

## Context
The v1 rule orders `forecast + safety stock`, where the safety stock is the
headroom to the upper forecast quantile. It treats a unit too many and a unit
too few as equally bad. For fresh goods they are not: a leftover unit costs its
purchase price once it expires, a missed sale costs the margin.

## Decision
1. Add a **newsvendor target** (`replenishment/newsvendor.py`): cover demand up
   to the critical ratio `CR = margin / (margin + cost * overage_factor)`, with
   the standard deviation taken from the calibrated 80 % interval.
2. Evaluate policies by **replaying history** (`replenishment/replay.py`) instead
   of arguing from theory: four policies (naive, v1 rule, newsvendor, planner)
   are played day by day over three months with FEFO stock, walk-forward models
   and only information available at order time. Stock is conserved by test.
3. The newsvendor's `overage_factor` (share of a leftover unit's cost that is
   really lost) is **estimated per SKU** on the 60 days *before* the replay
   window, from a small grid. The planner receives the same value as its
   leftover cost factor.

## Why not the textbook single-period newsvendor
With a 40 % margin and 60 % cost the plain ratio is 0.40, so the target falls
*below* expected demand. In the replay this lost to the v1 rule (fill rate
94-96 %), because leftover stock is mostly sold the next day and is not waste.
Estimating the carry-over per SKU raises the ratio (0.47 for 2-day bread, about
0.9 for longer-lived goods) and the policy then wins. Both results are kept in
the documentation so the reasoning can be checked.

## Consequences
* On synthetic data the newsvendor earned about +0.4 percentage points more
  profit than the v1 rule and cut waste cost by about a third, at 99.3 % fill
  rate; it won 11 of 14 weeks. That is a mechanics result, **not** evidence of
  real savings: recorded sales equal demand (no censoring) and costs are assumed.
* Several SKUs sit at the lowest grid value (0.05); a finer grid is future work.
* Humans still approve every order. The newsvendor changes the *proposal*, and
  GenAI still never decides quantities (ADR 0001).
* Real use needs censored-demand handling (stock-outs hide demand), a pilot
  with a control group, and supplier-specific costs.
