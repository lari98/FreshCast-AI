"""Deterministic explanations: the no-AI fallback and the test oracle."""

from __future__ import annotations

from freshcast.assistant.facts import ExplanationFacts
from freshcast.assistant.prompt import Language

_EN = (
    "For {product} ({sku}) at store {store}, demand in the planning window is "
    "forecast at {forecast} units plus a safety buffer of {safety}, giving a "
    "target of {target} units. {usable} units are sellable when the delivery "
    "arrives on {arrival} ({expiring} units will expire before then) and "
    "{incoming} units are already on the way. The system therefore proposes "
    "ordering {order} units in packs of {pack}."
)
_DE = (
    "Für {product} ({sku}) in der Filiale {store} wird im Planungszeitraum ein "
    "Bedarf von {forecast} Stück plus {safety} Stück Sicherheitsbestand "
    "erwartet, also ein Zielbestand von {target} Stück. Bei Lieferung am "
    "{arrival} sind {usable} Stück verkaufsfähig ({expiring} Stück laufen vorher "
    "ab), und {incoming} Stück sind bereits unterwegs. Das System schlägt daher "
    "eine Bestellung von {order} Stück in Packungen zu {pack} vor."
)
_EN_END = " This is a proposal only: a store manager must review and approve it before any order is placed."  # noqa: E501
_DE_END = " Das ist nur ein Vorschlag: Eine Filialleitung muss ihn prüfen und freigeben, bevor bestellt wird."  # noqa: E501
_EN_BLOCKED = " {blocked} units are on hold or recalled and are excluded."
_DE_BLOCKED = " {blocked} Stück sind gesperrt oder zurückgerufen und ausgeschlossen."


def render_template(facts: ExplanationFacts, language: Language) -> str:
    """Render the standard explanation in German or English."""
    body, end, blocked = (
        (_DE, _DE_END, _DE_BLOCKED) if language == "de" else (_EN, _EN_END, _EN_BLOCKED)
    )
    text = body.format(
        product=facts.product_name,
        sku=facts.sku,
        store=facts.store_id,
        forecast=facts.forecast_units,
        safety=facts.safety_stock_units,
        target=facts.target_stock_units,
        usable=facts.usable_stock_units,
        expiring=facts.expiring_stock_units,
        incoming=facts.incoming_units,
        arrival=facts.arrival_date.isoformat(),
        order=facts.recommended_order_units,
        pack=facts.order_multiple,
    )
    if facts.blocked_units > 0:
        text += blocked.format(blocked=facts.blocked_units)
    return text + end
