# ADR 0001: Deterministic core; generative AI explains only

Status: accepted (2026-11-01)

Context: order quantities affect cost and food waste and must be auditable.

Decision: quantities come from ML forecasts plus deterministic rules. Amazon
Bedrock receives structured facts and only explains them; it never invents or
changes numbers. Orders require human approval.

Consequences: reproducible, testable decisions; simpler EU AI Act documentation.
