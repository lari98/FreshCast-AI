# Architecture overview

POS/inventory/weather -> FastAPI + PostgreSQL (outbox) -> EventBridge/SQS ->
Lambda incremental workers -> forecasts + order proposals -> dashboard.
S3 feature data -> SageMaker training -> registry -> versioned forecasts.
Bedrock explains structured facts. Details are added per phase.
