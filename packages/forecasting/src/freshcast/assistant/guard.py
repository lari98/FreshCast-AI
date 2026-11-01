"""Output checks: reject any answer that is not fully grounded in the facts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from freshcast.assistant.facts import ExplanationFacts

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
_APPROVAL = ("approv", "freigab", "freigeb", "genehmig", "review", "prüf")
_BLOCKED = ("hold", "recall", "gesperrt", "blockiert", "rückruf", "sperr")


def _parse(token: str) -> Decimal | None:
    """Parse '1.234', '1,234', '3,5' or '3.5' into a Decimal."""
    if _THOUSANDS.match(token):
        token = re.sub(r"[.,]", "", token)
    else:
        token = token.replace(",", ".")
    try:
        return Decimal(token)
    except InvalidOperation:  # pragma: no cover - regex guarantees digits
        return None


def extract_numbers(text: str) -> list[Decimal]:
    """Return every number in the text, locale-aware."""
    numbers: list[Decimal] = []
    for token in _NUMBER.findall(text):
        value = _parse(token)
        if value is not None:
            numbers.append(value)
    return numbers


def check_answer(text: str, facts: ExplanationFacts) -> tuple[str, ...]:
    """Return violation codes; an empty tuple means the answer may be shown."""
    violations: list[str] = []
    if not text.strip():
        return ("empty",)
    allowed = facts.allowed_numbers()
    invented = sorted({n for n in extract_numbers(text) if n not in allowed})
    violations += [f"ungrounded_number:{n}" for n in invented]
    lower = text.lower()
    if facts.requires_human_approval and not any(w in lower for w in _APPROVAL):
        violations.append("missing_approval_notice")
    if facts.blocked_units > 0 and not any(w in lower for w in _BLOCKED):
        violations.append("missing_blocked_stock_notice")
    return tuple(violations)
