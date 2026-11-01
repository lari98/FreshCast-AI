"""Contract tests for the change-event schema."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from freshcast.events.contracts import (
    ChangeType,
    ForecastChangeEvent,
    affected_partition,
)


def _event(**overrides: object) -> ForecastChangeEvent:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "event_type": ChangeType.PRICE_UPDATED,
        "store_id": "DE-MUC-017",
        "sku": "SKU-421",
        "occurred_at": datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        "entity_version": 1,
    }
    base.update(overrides)
    return ForecastChangeEvent(**base)  # type: ignore[arg-type]


def test_valid_event_and_partition_key() -> None:
    assert affected_partition(_event()) == "DE-MUC-017:SKU-421"


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        _event(occurred_at=datetime(2026, 11, 1, 12, 0))  # noqa: DTZ001


def test_unknown_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _event(unexpected="x")


def test_event_is_immutable() -> None:
    with pytest.raises(ValidationError):
        _event().sku = "OTHER"  # type: ignore[misc]


def test_entity_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _event(entity_version=0)
