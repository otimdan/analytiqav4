"""Guards on regime routing after the orientation regime was removed.

Explore mode is free-form, so help-shaped openers must reach the analysis path
instead of being intercepted by a recap regime.
"""

import asyncio

import pytest

from app.orchestrator import classifier
from app.llm.schemas import ClassificationResult


HELP_SHAPED = [
    "please help me analyze my data",
    "help me analyze my data",
    "what should i do next",
    "guide me",
    "i don't know what to do",
]


@pytest.mark.parametrize("message", HELP_SHAPED)
def test_help_openers_are_not_intercepted_by_a_rule(message):
    """These used to match a deterministic orientation rule."""
    hit = next((r for p, r in classifier._RULE_PATTERNS if p.search(message)), None)
    assert hit is None, f"{message!r} still matches a rule routing to {hit!r}"


def test_no_rule_routes_to_orientation():
    assert all(regime != "orientation" for _, regime in classifier._RULE_PATTERNS)


def test_unknown_regime_from_the_model_falls_back_to_exploratory(monkeypatch):
    """`regime` is an unconstrained str; a stale "orientation" would otherwise
    reach _dispatch and hit its "I wasn't sure how to handle that" dead end."""

    async def fake_classifier(**kwargs):
        return ClassificationResult(regime="orientation", confidence="llm_low")

    monkeypatch.setattr(classifier, "call_classifier_model", fake_classifier)
    result = asyncio.run(
        classifier.classify_intent(message="tell me something", recent_messages=[])
    )
    assert result.regime == "exploratory"


def test_known_regime_from_the_model_is_preserved(monkeypatch):
    async def fake_classifier(**kwargs):
        return ClassificationResult(regime="confirmatory", confidence="llm_high")

    monkeypatch.setattr(classifier, "call_classifier_model", fake_classifier)
    result = asyncio.run(
        classifier.classify_intent(message="tell me something", recent_messages=[])
    )
    assert result.regime == "confirmatory"
