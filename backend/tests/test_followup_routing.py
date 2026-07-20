"""Follow-up questions that refer to the previous answer.

"Explain to me the above results" matched no rule, fell to the LLM classifier
with only a truncated slice of the last reply for context, and got routed to
advisory — which was prompted to answer from the dataset profile alone. The user
asked about a meta-analysis and received a column-by-column schema dump.
"""

import pytest

from app.orchestrator.classifier import _RULE_PATTERNS


def route(message: str) -> str:
    return next((regime for pattern, regime in _RULE_PATTERNS if pattern.search(message)), "llm")


@pytest.mark.parametrize(
    "message",
    [
        "Explain to me the above results",
        "explain these results",
        "what do these results mean",
        "what does this mean",
        "interpret the output above",
        "explain that",
        "Interpret",
        "summarise the above findings",
        "walk me through these numbers",
        "unpack that analysis",
    ],
)
def test_followups_route_deterministically(message):
    assert route(message) == "advisory"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # "mean" is in the pedagogy term list (arithmetic mean), so ordering
        # between the follow-up rules and pedagogy is load-bearing in both
        # directions. A pronoun is what separates them.
        ("what does a p-value mean", "pedagogy"),
        ("what does an anova mean", "pedagogy"),
        ("explain a p-value", "pedagogy"),
        ("what is a t-test", "pedagogy"),
        ("define standard deviation", "pedagogy"),
        ("run a t-test on age and income", "confirmatory"),
        ("is the difference significant", "confirmatory"),
        ("drop rows with missing values", "cleaning"),
        ("how many rows are there", "advisory"),
        ("generate a report", "meta"),
    ],
)
def test_no_regressions_from_the_follow_up_rules(message, expected):
    assert route(message) == expected


def test_what_does_x_mean_reaches_pedagogy_at_all():
    """`what does .+ mean` was greedy: it swallowed the statistics term, so the
    trailing term the pattern required was never present and the whole phrasing
    fell through to the LLM classifier."""
    assert route("what does a p-value mean") == "pedagogy"
