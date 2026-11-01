"""Text-model ports: Amazon Bedrock Converse adapter and a test double."""

from __future__ import annotations

from typing import Any, Protocol


class TextModel(Protocol):
    """Minimal text-generation port."""

    model_id: str

    def generate(self, system: str, user: str) -> str:
        """Return the model's text answer or raise."""


class BedrockConverseModel:
    """Amazon Bedrock via the Converse API.

    The model id is configuration, never hard-coded: availability, regional
    inference routing, cost and data terms must be verified per account
    (use an EU inference profile to keep processing in the EU).
    """

    def __init__(
        self,
        model_id: str,
        region: str = "eu-central-1",
        client: Any | None = None,
        max_tokens: int = 400,
    ) -> None:
        """Create the adapter; ``client`` is injectable for tests."""
        if not model_id.strip():
            raise ValueError("model_id is required")
        self.model_id = model_id
        self._max_tokens = max_tokens
        if client is None:
            import boto3  # noqa: PLC0415 - optional dependency (extra: aws)

            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client

    def generate(self, system: str, user: str) -> str:
        """Call Converse with temperature 0 for repeatable output."""
        response = self._client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.0},
        )
        parts = response["output"]["message"]["content"]
        return "".join(part.get("text", "") for part in parts).strip()


class FakeModel:
    """Deterministic stand-in used in tests and offline demos."""

    def __init__(self, answer: str = "", error: Exception | None = None) -> None:
        """Return ``answer`` or raise ``error``; remember the last prompt."""
        self.model_id = "fake-model"
        self._answer, self._error = answer, error
        self.last_system = ""
        self.last_user = ""

    def generate(self, system: str, user: str) -> str:
        """Record the prompt and return the canned answer."""
        self.last_system, self.last_user = system, user
        if self._error is not None:
            raise self._error
        return self._answer
