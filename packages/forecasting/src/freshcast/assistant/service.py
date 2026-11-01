"""Explanation service: model answer if grounded, deterministic text otherwise."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from freshcast.assistant.client import TextModel
from freshcast.assistant.facts import ExplanationFacts
from freshcast.assistant.guard import check_answer
from freshcast.assistant.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    Language,
    build_user_message,
)
from freshcast.assistant.templates import render_template

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Explanation:
    """An explanation with the provenance needed for transparency."""

    text: str
    language: Language
    source: Literal["model", "template"]
    violations: tuple[str, ...]
    prompt_version: str
    model_id: str | None

    @property
    def ai_generated(self) -> bool:
        """True only when the text came from the language model."""
        return self.source == "model"


def explain(
    facts: ExplanationFacts, language: Language, model: TextModel | None = None
) -> Explanation:
    """Explain a proposal; never show text that fails the grounding checks."""

    def fallback(violations: tuple[str, ...]) -> Explanation:
        return Explanation(
            text=render_template(facts, language),
            language=language,
            source="template",
            violations=violations,
            prompt_version=PROMPT_VERSION,
            model_id=model.model_id if model else None,
        )

    if model is None:
        return fallback(())
    try:
        answer = model.generate(SYSTEM_PROMPT, build_user_message(facts, language))
    except Exception as exc:  # noqa: BLE001 - any model failure degrades gracefully
        logger.warning("model call failed", extra={"error": type(exc).__name__})
        return fallback(("model_error",))
    violations = check_answer(answer, facts)
    if violations:
        logger.warning("answer rejected", extra={"violations": list(violations)})
        return fallback(violations)
    return Explanation(
        text=answer.strip(),
        language=language,
        source="model",
        violations=(),
        prompt_version=PROMPT_VERSION,
        model_id=model.model_id,
    )
