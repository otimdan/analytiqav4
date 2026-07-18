"""Phase B integration tests for verified regression (deterministic parts, no LLM/E2B):
routing detection, column matching, parsing real model output into artifact
content, and report rendering."""
import os
import pytest

from tests import fixtures as F
from tests._local_sandbox import write_csv, run_script
from app.stats_engine.regression import render_regression
from app.regimes.confirmatory import _is_regression_request, _match_column, _parse_regression_output
from app.reports.generator import _format_regression


def _real_linear_output():
    code = render_regression("linear", "exam_score", ["hours_studied", "cohort"], ["cohort"])
    path = write_csv(F.linear_regression_dataset())
    try:
        return run_script(code, path)
    finally:
        os.remove(path)


def _real_logistic_output():
    code = render_regression("logistic", "passed", ["hours_studied"], [])
    path = write_csv(F.logistic_regression_dataset())
    try:
        return run_script(code, path)
    finally:
        os.remove(path)


# ── Routing ──────────────────────────────────────────────────────────────────
class TestRegressionRouting:
    @pytest.mark.parametrize("msg", [
        "fit a linear regression of exam_score on hours_studied and cohort",
        "predict exam_score from hours_studied",
        "regress score on age and sex",
        "model exam_score using hours and study_method",
        "compare groups controlling for age",
        "run a logistic regression",
    ])
    def test_detected(self, msg):
        assert _is_regression_request(msg) is True

    @pytest.mark.parametrize("msg", [
        "run a t-test on exam_score by cohort",
        "is hours related to score",
        "plot exam_score",
    ])
    def test_not_detected(self, msg):
        assert _is_regression_request(msg) is False


# ── Column matching ──────────────────────────────────────────────────────────
def test_column_matching():
    cols = ["exam_score", "hours_studied", "cohort"]
    assert _match_column("exam_score", cols) == "exam_score"
    assert _match_column("Exam_Score", cols) == "exam_score"     # case-insensitive
    assert _match_column("hours", cols) == "hours_studied"       # substring
    assert _match_column("nonexistent", cols) is None


# ── Parsing real output into artifact content ────────────────────────────────
@pytest.fixture(scope="module")
def content():
    resolved = {"model_type": "linear", "outcome": "exam_score", "predictors": ["hours_studied", "cohort"], "categoricals": ["cohort"]}
    return _parse_regression_output(_real_linear_output(), resolved)


class TestParseLinear:
    def test_required_fields_for_validator(self, content):
        # test_result artifacts must carry test_name + p_value.
        assert content["test_name"] and content["p_value"] is not None

    def test_fit_stats(self, content):
        assert content["r_squared"] > 0.9 and content["n"] == 200

    def test_coefficients_parsed(self, content):
        names = {c["name"] for c in content["coefficients"]}
        assert "hours_studied" in names
        hours = next(c for c in content["coefficients"] if c["name"] == "hours_studied")
        assert abs(hours["coef"] - 4.0) < 0.5 and hours["ci_low"] < hours["ci_high"]

    def test_diagnostics_parsed(self, content):
        d = content["diagnostics"]
        assert d["durbin_watson"] is not None
        assert "hours_studied" in d["vif"]


class TestParseLogistic:
    def test_odds_ratios_parsed(self):
        resolved = {"model_type": "logistic", "outcome": "passed", "predictors": ["hours_studied"], "categoricals": []}
        content = _parse_regression_output(_real_logistic_output(), resolved)
        assert content["display_name"] == "Logistic Regression"
        hours = next(c for c in content["coefficients"] if c["name"] == "hours_studied")
        assert hours["odds_ratio"] is not None and hours["coef"] > 0


# ── Report rendering ─────────────────────────────────────────────────────────
def test_report_renders_regression_table():
    resolved = {"model_type": "linear", "outcome": "exam_score", "predictors": ["hours_studied", "cohort"], "categoricals": ["cohort"]}
    content = _parse_regression_output(_real_linear_output(), resolved)
    md = _format_regression(content)
    assert "Linear Regression" in md and "| Predictor |" in md and "hours_studied" in md
    assert "R²" in md
