# Replenishment v2 (phase 5)

`replenishment/engine.py` is the quick single-target rule; `replenishment/planner.py`
is the timeline-based planner.

**Simulation (`simulate`)** - per day: receive deliveries, write off lots past
their use-by date (waste), sell oldest-first (FEFO), count unmet demand (lost
sales). Blocked lots (hold/recall) are never sold, never counted as waste.

**Planner (`plan_order`)** - runs the simulation for lower / point / upper demand
scenarios (from the 10 % / 50 % / 90 % forecast) for every pack-rounded order
size, and chooses the size with the lowest weighted cost:

`cost = w x (waste x unit_cost + lost x unit_margin + leftover x unit_cost x factor)`

The delivery day follows the supplier lead time and allowed delivery weekdays.
Ties keep the smaller order. Output is a proposal that needs human approval.

Assumptions: use-by date is the last sellable day; weights (0.2/0.6/0.2) and the
leftover factor (0.3) are tunable business parameters, not learned values.
