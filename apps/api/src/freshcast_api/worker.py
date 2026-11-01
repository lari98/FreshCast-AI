"""AWS Lambda entry point: SQS FIFO -> EventProcessor.

Uses SQS partial batch responses: only messages whose processing exhausted its
retries are reported as failures, so SQS redrives them (and finally moves them
to the dead-letter queue) without re-running the successful ones.

NOTE: ``default_recompute`` only logs for now. The real feature, forecast and
proposal recomputation is wired in when the training/inference pipeline lands.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session, sessionmaker

from freshcast.events.contracts import ForecastChangeEvent
from freshcast.events.processor import (
    EventProcessor,
    Outcome,
    Recomputer,
    RetryPolicy,
    Stage,
)
from freshcast_api.config import Settings
from freshcast_api.db import make_engine, make_session_factory
from freshcast_api.state_store import SqlStateStore

logger = logging.getLogger(__name__)
_FACTORY: sessionmaker[Session] | None = None


def default_recompute(partition: str, stage: Stage) -> None:
    """Log what would be recomputed (placeholder until the pipeline is wired)."""
    logger.info("recompute", extra={"partition": partition, "stage": stage.value})


class _Collector:
    """Dead-letter sink that remembers which events failed."""

    def __init__(self) -> None:
        """Start empty."""
        self.failed: set[str] = set()

    def put(self, event: ForecastChangeEvent, error: str, attempts: int) -> None:
        """Remember the failed event id (SQS owns the real DLQ)."""
        del error, attempts
        self.failed.add(str(event.event_id))


def database_url_from_secret(secret_string: str) -> str:
    """Build a SQLAlchemy URL from an RDS-generated Secrets Manager secret."""
    secret = json.loads(secret_string)
    user, password = (
        quote(secret["username"], safe=""),
        quote(secret["password"], safe=""),
    )
    return (
        f"postgresql+psycopg://{user}:{password}"
        f"@{secret['host']}:{secret.get('port', 5432)}/{secret['dbname']}"
    )


def _resolve_database_url() -> str:
    arn = os.environ.get("FRESHCAST_DB_SECRET_ARN")
    if not arn:
        return Settings().database_url
    import boto3  # noqa: PLC0415 - only available/needed inside Lambda

    value = boto3.client("secretsmanager").get_secret_value(SecretId=arn)
    return database_url_from_secret(value["SecretString"])


def _factory() -> sessionmaker[Session]:
    global _FACTORY  # noqa: PLW0603 - reuse connections across warm invocations
    if _FACTORY is None:
        _FACTORY = make_session_factory(make_engine(_resolve_database_url()))
    return _FACTORY


def process_sqs_batch(
    records: list[dict[str, Any]],
    factory: sessionmaker[Session],
    recompute: Recomputer = default_recompute,
) -> dict[str, list[dict[str, str]]]:
    """Process one SQS batch and return the partial-batch response."""
    collector = _Collector()
    processor = EventProcessor(
        SqlStateStore(factory), recompute, collector, RetryPolicy(2, 0.2)
    )
    parsed: list[tuple[str, ForecastChangeEvent]] = []
    failures: list[dict[str, str]] = []
    for record in records:
        try:
            event = ForecastChangeEvent.model_validate_json(record["body"])
        except ValueError:
            # Malformed message: retrying cannot help; let SQS dead-letter it.
            failures.append({"itemIdentifier": record["messageId"]})
            continue
        parsed.append((record["messageId"], event))

    results = processor.process_batch([e for _, e in parsed])
    for (message_id, _), result in zip(parsed, results, strict=True):
        if result.outcome is Outcome.DEAD_LETTERED:
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Lambda handler."""
    del context
    response = process_sqs_batch(event.get("Records", []), _factory())
    logger.info(json.dumps({"failed": len(response["batchItemFailures"])}))
    return response
