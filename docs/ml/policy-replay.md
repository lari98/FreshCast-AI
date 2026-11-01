# Policy replay (synthetic data)

Window: 2025-10-01 to 2025-12-31 (92 days, 56 store/SKU series), after a 7-day warm-up. Models are refitted every 30 days on earlier data only. Assumed costs: purchase cost 60 %, margin 40 % of the list price.

## CHF

| Policy | Fill rate | Waste rate | Waste cost | Lost margin | Profit | Profit vs naive |
|---|---|---|---|---|---|---|
| naive | 94.2% | 0.6% | 609 | 3,451 | 54,347 | - |
| rule_v1 | 99.7% | 1.4% | 1,527 | 193 | 56,686 | +4.3% |
| newsvendor | 99.3% | 0.8% | 932 | 498 | 56,976 | +4.8% |
| planner | 98.3% | 0.4% | 476 | 1,284 | 56,646 | +4.2% |

## EUR

| Policy | Fill rate | Waste rate | Waste cost | Lost margin | Profit | Profit vs naive |
|---|---|---|---|---|---|---|
| naive | 94.3% | 0.7% | 1,544 | 7,527 | 129,780 | - |
| rule_v1 | 99.7% | 1.2% | 3,108 | 390 | 135,355 | +4.3% |
| newsvendor | 99.3% | 0.7% | 1,957 | 971 | 135,924 | +4.7% |
| planner | 98.3% | 0.4% | 1,067 | 2,751 | 135,033 | +4.0% |

## Paired weekly check

The newsvendor policy earned more profit than the v1 rule in 11 of 14 weeks. A small overall gain with few winning weeks would be noise; read the profit column together with this line.

## Tuned overage factors

Share of a leftover unit's cost that is really lost. Chosen per SKU from a grid on the 60 days *before* the window (never on the evaluated days). 0.05 is the lowest value in the grid.

| SKU | Overage factor | Critical ratio (cost 60 %, margin 40 %) |
|---|---|---|
| BREAD-WHEAT-750G | 0.75 | 0.47 |
| CHICKEN-BREAST-500G | 0.05 | 0.93 |
| MILK-1L | 0.05 | 0.93 |
| SALAD-MIXED-200G | 0.10 | 0.87 |
| SALMON-FILLET-250G | 0.20 | 0.77 |
| STRAWBERRY-500G | 0.05 | 0.93 |
| TOMATO-500G | 0.05 | 0.93 |
| YOGURT-500G | 0.05 | 0.93 |

## How to read this

* Recorded sales stand in for demand (no censoring) and the data is simulated, so this shows how the policies behave, not what a real store would save.
* With a plain single-period newsvendor (overage factor 1.0) the target falls below expected demand and loses to the v1 rule, because leftovers are mostly sold the next day. Estimating the carry-over per SKU fixes that; see ADR 0004.
* A policy that wins here still needs a real pilot before any claim.
