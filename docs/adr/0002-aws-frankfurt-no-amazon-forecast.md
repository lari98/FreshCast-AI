# ADR 0002: Default region eu-central-1; no Amazon Forecast

Status: accepted (2026-11-01)

Decision: deploy to AWS Frankfurt by default; use SageMaker AI with LightGBM
instead of Amazon Forecast (closed to new customers). Verify Bedrock model and
inference-region availability per account before use. EU hosting alone does not
settle international-transfer questions.
