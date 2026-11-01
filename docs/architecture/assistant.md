# Grounded assistant (phase 8)

Principle: the language model **explains**, deterministic code **decides**.

Flow: proposal -> `ExplanationFacts` (typed, sanitised) -> prompt v1.0.0 -> model
(Amazon Bedrock Converse, temperature 0) -> **guard** -> shown, else template.

| Control | What it does |
|---|---|
| Facts only | Prompt contains the facts as JSON inside `<facts>`; rules say it is data, not instructions |
| Number guard | Every number in the answer must exist in the facts (locale-aware: `1.234`, `3,5`); dates compared by parts |
| Required content | Must state that a manager approves; must mention blocked/recalled units when present |
| Injection hygiene | Product text is stripped of control characters and brackets, capped at 80 chars; digits in free text are not trusted (only size units like `500 g`) |
| Graceful fallback | Model error, empty or rejected answer -> deterministic German/English template |
| Transparency | API returns `source`, `ai_generated`, `prompt_version`, violations and a disclaimer; each explanation is audit-logged |

Configuration: set `FRESHCAST_BEDROCK_MODEL_ID` (model or EU inference-profile id)
to enable the model. Unset = template only. Verify model availability, EU
processing/inference routing, cost and data terms in your AWS account first; grant
the API role `bedrock:InvokeModel` for that model only. Consider Bedrock Guardrails
as an extra layer, not a replacement for the guard.

Evaluation (`tests/test_assistant.py`): grounded answers pass in DE and EN;
invented quantities (97, 130, 777, 9999), missing approval notice, missing
recall notice, empty output, model timeouts and prompt-injection product names
all fall back safely. Re-run on every prompt or model change; bump `PROMPT_VERSION`.

Limits: the guard checks numbers and mandatory statements, not tone or every
possible wrong claim in prose. It is not a legal or food-safety advisor.
