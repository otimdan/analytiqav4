"""Golden tests for verified regression (Goal 1) — deterministic core.

Runs the REAL statsmodels templates locally (no E2B) and checks they recover the
known coefficients of engineered datasets, and that the resolver picks the right
model family and validates inputs. Locks in "verified regression, right answer."
"""
import re
import pytest

from tests import fixtures as F
from tests._local_sandbox import profile_locally, run_script, write_csv
from app.stats_engine.regression import resolve_model, render_regression
import os


def _run_regression(df, model_type, outcome, predictors, categoricals):
    code = render_regression(model_type, outcome, predictors, categoricals)
    path = write_csv(df)
    try:
        return run_script(code, path)
    finally:
        os.remove(path)


def _coef(out, name):
    m = re.search(rf"^{re.escape(name)}: coef=([\-0-9.]+)", out, re.MULTILINE)
    return float(m.group(1)) if m else None


def _field(out, label):
    m = re.search(rf"{re.escape(label)}[:\s]+([\-0-9.eE]+)", out)
    return float(m.group(1)) if m else None


# ── Model resolution ─────────────────────────────────────────────────────────
class TestResolveModel:
    def test_linear_for_numeric_outcome(self):
        prof = profile_locally(F.linear_regression_dataset())
        r = resolve_model("exam_score", ["hours_studied", "cohort"], prof)
        assert r["ok"] and r["model_type"] == "linear"
        assert r["categoricals"] == ["cohort"]

    def test_logistic_for_binary_outcome(self):
        prof = profile_locally(F.logistic_regression_dataset())
        r = resolve_model("passed", ["hours_studied"], prof)
        assert r["ok"] and r["model_type"] == "logistic"

    def test_rejects_outcome_as_its_own_predictor(self):
        prof = profile_locally(F.linear_regression_dataset())
        r = resolve_model("exam_score", ["exam_score"], prof)
        assert r["ok"] is False

    def test_rejects_no_predictors(self):
        prof = profile_locally(F.linear_regression_dataset())
        assert resolve_model("exam_score", [], prof)["ok"] is False


@pytest.fixture(scope="module")
def linear_out():
    return _run_regression(F.linear_regression_dataset(), "linear", "exam_score",
                           ["hours_studied", "cohort"], ["cohort"])


@pytest.fixture(scope="module")
def logistic_out():
    return _run_regression(F.logistic_regression_dataset(), "logistic", "passed",
                           ["hours_studied"], [])


# ── Linear regression recovers known coefficients ────────────────────────────
class TestLinearRegression:
    def test_recovers_slope(self, linear_out):
        # true hours coefficient = 4
        assert abs(_coef(linear_out, "hours_studied") - 4.0) < 0.5

    def test_recovers_group_effect(self, linear_out):
        # true cohort==morning effect = -6 (evening is the dropped reference)
        c = _coef(linear_out, "cohort_morning")
        assert c is not None and abs(c - (-6.0)) < 1.5

    def test_high_r_squared(self, linear_out):
        assert _field(linear_out, "R-squared") > 0.9

    def test_reports_diagnostics(self, linear_out):
        assert "VIF" in linear_out and "Durbin-Watson" in linear_out and "Breusch-Pagan" in linear_out
        assert "Residual normality p" in linear_out

    def test_model_significant(self, linear_out):
        assert _field(linear_out, "P-value") < 0.05


# ── Logistic regression recovers direction ───────────────────────────────────
class TestLogisticRegression:
    def test_positive_significant_predictor(self, logistic_out):
        # true logit slope = +0.6; more hours -> higher P(pass)
        c = _coef(logistic_out, "hours_studied")
        assert c is not None and c > 0

    def test_reports_odds_ratio(self, logistic_out):
        assert "or=" in logistic_out and "Pseudo R-squared" in logistic_out


# ── Injection safety ─────────────────────────────────────────────────────────
def test_regression_render_injection_safe():
    evil = "y'] ); import os; os.system('x')  #"
    code = render_regression("linear", "score", [evil, "age"], [])
    assert repr(evil) in code
    assert "os.system('x')" not in code.replace(repr(evil), "")
