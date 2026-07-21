"""Resolving which columns a plain-English question refers to.

Every one of these failed against the old `col.lower() in message.lower()` rule,
because column names carry underscores and users do not. Confirmatory answered
"I need two columns to run a test" to questions that named both, and charts were
logged with no variables_involved — which also broke the follow-up path.
"""

import pytest

from app.stats_engine.column_matcher import match_columns

COLUMNS = [
    "student_id", "gender", "age", "study_hours_per_week", "attendance_rate",
    "part_time_job", "stress_level", "exam_score", "satisfaction",
]

PROFILE = {
    "columns": {
        "gender": {"top_values": {"Male": 45, "Female": 45}},
        "stress_level": {"top_values": {"High": 30, "Medium": 30, "Low": 30}},
        "part_time_job": {"top_values": {"Yes": 40, "No": 50}},
    }
}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # Verbatim from the section-A run that exposed this.
        ("Does exam score differ across stress levels?", {"exam_score", "stress_level"}),
        ("I meant for the previous prompt study hours and exam score", {"study_hours_per_week", "exam_score"}),
        ("I want to see how study hours relate to exam score", {"study_hours_per_week", "exam_score"}),
        # Underscore/space and plural handling.
        ("Plot the distribution of exam scores", {"exam_score"}),
        ("compare attendance rate and satisfaction", {"attendance_rate", "satisfaction"}),
        ("does part time job affect exam score", {"part_time_job", "exam_score"}),
        ("show me student_id", {"student_id"}),
    ],
)
def test_natural_phrasing_resolves(message, expected):
    assert set(match_columns(message, COLUMNS, PROFILE)) == expected


def test_a_column_named_only_by_its_values_is_inferred():
    """"male and female" is how people name a gender column without naming it."""
    assert set(match_columns(
        "Do exam scores differ between male and female students?", COLUMNS, PROFILE
    )) == {"exam_score", "gender"}


def test_one_value_alone_does_not_imply_a_column():
    """Two distinct values are required — one is too weak and misfires on prose."""
    assert "part_time_job" not in match_columns("is that a yes", COLUMNS, PROFILE)


@pytest.mark.parametrize(
    "message",
    [
        "Is that relationship statistically significant?",
        "What is a p-value?",
        "how many rows are there",
        "generate a report",
    ],
)
def test_messages_naming_no_column_stay_empty(message):
    """A follow-up naming nothing must fall through to focus_variables, not
    match something spurious."""
    assert match_columns(message, COLUMNS, PROFILE) == []


def test_substrings_do_not_match():
    """'age' must not match inside 'average' — the reason matching is on token
    sequences rather than substrings."""
    assert match_columns("what is the average", ["age"], None) == []
    assert match_columns("what is the average age", ["age"], None) == ["age"]


def test_identifier_columns_are_not_prefix_matched():
    """'students' matched student_id and beat the gender column it should have
    found. An id is never the subject of an analysis."""
    assert "student_id" not in match_columns("compare male and female students", COLUMNS, PROFILE)
