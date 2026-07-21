"""Scatter axes must agree with the chart title, and volunteered inference must
be badged.

Both came out of one section-A run: a chart titled "exam_score vs
study_hours_per_week" plotted exam_score horizontally, reading as though study
hours were the outcome; and the same turn reported r, R², a coefficient, SE and
p < 0.0001 with no "not verified" badge.
"""

import pytest

from app.regimes.exploratory import _code_did_inference
from app.stats_engine.chart_selector import recommend_chart

NUMERIC_PROFILE = {
    "columns": {
        "exam_score": {"pandas_dtype": "float64", "unique_count": 80, "likely_categorical": False},
        "study_hours_per_week": {"pandas_dtype": "float64", "unique_count": 85, "likely_categorical": False},
    }
}


def test_scatter_title_and_axes_agree():
    """"Y vs X": the first-named column belongs on the y-axis. The directive used
    to put it on x while titling it the other way round."""
    rec = recommend_chart(["exam_score", "study_hours_per_week"], NUMERIC_PROFILE)
    assert rec.rationale == "exam_score vs study_hours_per_week"
    assert "`study_hours_per_week` on the x-axis" in rec.directive
    assert "`exam_score` on the y-axis" in rec.directive


def test_scatter_axes_follow_the_named_order():
    """Reversing the request reverses the axes, so the title stays truthful."""
    rec = recommend_chart(["study_hours_per_week", "exam_score"], NUMERIC_PROFILE)
    assert rec.rationale == "study_hours_per_week vs exam_score"
    assert "`exam_score` on the x-axis" in rec.directive
    assert "`study_hours_per_week` on the y-axis" in rec.directive


@pytest.mark.parametrize(
    "code",
    [
        "r, p = stats.pearsonr(df['a'], df['b'])",
        "res = stats.linregress(df['a'], df['b'])",
        "t, p = stats.ttest_ind(a, b)",
        "f, p = stats.f_oneway(g1, g2, g3)",
        "model = LinearRegression().fit(X, y)",
        "import statsmodels.api as sm",
        "chi2, p, dof, exp = stats.chi2_contingency(tab)",
    ],
)
def test_inferential_code_is_detected(code):
    assert _code_did_inference([code]) is True


@pytest.mark.parametrize(
    "code",
    [
        "print(df['exam_score'].mean())",
        "df.groupby('gender')['exam_score'].describe()",
        "fig, ax = plt.subplots(); ax.hist(df['exam_score'])",
        "print(df.shape)",
    ],
)
def test_descriptive_code_is_not_badged(code):
    """Over-badging is its own failure: a caveat on every mean teaches users to
    ignore the caveat."""
    assert _code_did_inference([code]) is False
