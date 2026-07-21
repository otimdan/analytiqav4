"""Ordinal groups must be charted in their meaningful order, and p-values must
never print as zero.

Both came from one section-A run. A stress box plot came out High, Low, Medium
(pandas sorts alphabetically) under a narration describing "a clear downward
trend as stress increases" — the text and the picture disagreed. Separately the
verified templates printed p as 0.0000, which reads as a probability of exactly
zero; the model had to flag it in its own write-up.
"""

import pytest

from app.reports.stats_extract import _find_float
from app.stats_engine.chart_selector import ordinal_order, recommend_chart

PROFILE = {
    "columns": {
        "exam_score": {"pandas_dtype": "float64", "unique_count": 80, "likely_categorical": False},
        "stress_level": {"pandas_dtype": "object", "unique_count": 3,
                         "top_values": {"Medium": 36, "Low": 33, "High": 21}},
        "region": {"pandas_dtype": "object", "unique_count": 4,
                   "top_values": {"North": 20, "South": 15, "East": 10, "West": 8}},
        "severity": {"pandas_dtype": "object", "unique_count": 3,
                     "top_values": {"Severe": 5, "Mild": 20, "Moderate": 12}},
    }
}


def test_ordinal_values_are_ordered_meaningfully():
    assert ordinal_order("stress_level", PROFILE) == ["Low", "Medium", "High"]
    assert ordinal_order("severity", PROFILE) == ["Mild", "Moderate", "Severe"]


def test_unordered_categories_are_left_alone():
    """Imposing an order on genuinely nominal groups would be a different lie."""
    assert ordinal_order("region", PROFILE) is None


def test_box_directive_pins_the_order():
    rec = recommend_chart(["exam_score", "stress_level"], PROFILE)
    assert "['Low', 'Medium', 'High']" in rec.directive
    assert "NOT alphabetically" in rec.directive


def test_box_directive_stays_quiet_for_nominal_groups():
    assert "alphabetically" not in recommend_chart(["exam_score", "region"], PROFILE).directive


@pytest.mark.parametrize("p", [1.2e-18, 3e-5, 0.0173, 0.5])
def test_p_values_never_print_as_zero_and_still_parse(p):
    """`.4f` rendered anything under 0.00005 as '0.0000'. The replacement has to
    stay machine-readable: _find_float feeds the APA report, and a '< .001'
    string would parse as None and silently drop the p-value."""
    line = f"P-value: {p:.4g}"
    assert "0.0000" not in line
    parsed = _find_float("P-value", line)
    assert parsed is not None
    assert parsed == pytest.approx(p, rel=1e-3)
