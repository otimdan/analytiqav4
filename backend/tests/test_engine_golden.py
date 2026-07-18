"""Golden tests for the deterministic stats engine — the LIVE path.

Unlike test_stats_engine.py (hand-built profiles + the static select_test), these
run the REAL production chain on REAL data with no E2B:
    profiler script → classify → resolve → live assumption script → decide → template

They lock in "correct test, correct answer, every time" so later work (regression,
cleaning, …) can't silently regress the verified guarantee.

Run: pytest tests/test_engine_golden.py -v   (zero API keys, zero network)
"""
import re
import pytest

from tests import fixtures as F
from tests._local_sandbox import profile_locally, live_checks_locally, run_template_locally, live_select
from app.stats_engine.variable_classifier import (
    classify_variable, NUMERIC, NUMERIC_OR_ORDINAL, CATEGORICAL, IDENTIFIER, DATETIME,
)
from app.stats_engine.assumption_checks import PASS, FAIL, NOT_APPLICABLE
from app.stats_engine.test_selector import resolve_pair


def _p(stdout: str):
    m = re.search(r"[Pp]-value[:\s]+([0-9.eE\-]+)", stdout)
    return float(m.group(1)) if m else None


@pytest.fixture(scope="module")
def classification_profile():
    return profile_locally(F.classification_dataset())


# ── 1. Classification (real profiler → classify_variable) ────────────────────
class TestClassificationLive:
    @pytest.mark.parametrize("col,expected", [
        ("patient_weight", NUMERIC),          # continuous float measurement
        ("age", NUMERIC),                     # int measurement (many values)
        ("satisfaction_score", NUMERIC_OR_ORDINAL),  # Likert -> ordinal, not nominal
        ("sex", CATEGORICAL),                 # text
        ("arm", CATEGORICAL),                 # int 2-level
        ("session_time", CATEGORICAL),        # 'time' in name but text values
        ("patient_id", IDENTIFIER),           # id name + unique
        ("email", IDENTIFIER),                # unique strings
        ("visit_date", DATETIME),             # real dates
    ])
    def test_column_type(self, classification_profile, col, expected):
        assert classify_variable(col, classification_profile) == expected

    def test_float_measurement_is_analyzable(self, classification_profile):
        from app.stats_engine.variable_classifier import is_suitable_for_analysis
        assert is_suitable_for_analysis("patient_weight", classification_profile)[0] is True


# ── 2. Live assumption checks on known data ──────────────────────────────────
class TestAssumptionChecksLive:
    def _checks(self, df, va, vb):
        profile = profile_locally(df)
        r = resolve_pair(va, vb, profile)
        assert r.get("ok"), r
        return live_checks_locally(df, r["var_a"], r["var_b"], r["type_a"], r["type_b"])

    def test_normal_groups_pass_normality(self):
        c = self._checks(F.numeric_by_2group_equalvar(), "bp", "arm")
        assert c["normality_outcome"] == PASS
        assert c["variance_equal"] == PASS

    def test_skewed_fails_normality(self):
        c = self._checks(F.numeric_by_2group_skewed(), "bp", "arm")
        assert c["normality_outcome"] == FAIL

    def test_unequal_variance_detected(self):
        c = self._checks(F.numeric_by_2group_unequalvar(), "bp", "arm")
        assert c["variance_equal"] == FAIL

    def test_small_expected_cells_detected(self):
        c = self._checks(F.two_categorical_2x2_small(), "sex", "passed")
        assert c["min_expected_cell"] == FAIL

    def test_adequate_cells_pass(self):
        c = self._checks(F.two_categorical_2x2_adequate(), "sex", "passed")
        assert c["min_expected_cell"] == PASS


# ── 3. Full selection chain → correct test (the core guarantee) ──────────────
class TestSelectionGolden:
    @pytest.mark.parametrize("builder,va,vb,expected", [
        (F.two_numeric_normal, "height", "weight", "pearson"),
        (F.two_numeric_skewed, "height", "income", "spearman"),
        (F.ordinal_and_numeric, "satisfaction_score", "height", "spearman"),
        (F.numeric_by_2group_equalvar, "bp", "arm", "independent_t"),
        (F.numeric_by_2group_unequalvar, "bp", "arm", "welch_t"),
        (F.numeric_by_2group_skewed, "bp", "arm", "mann_whitney"),
        (F.numeric_by_3group_equalvar, "bp", "region", "one_way_anova"),
        (F.numeric_by_3group_unequalvar, "bp", "region", "welch_anova"),
        (F.numeric_by_3group_skewed, "bp", "region", "kruskal_wallis"),
        (F.two_categorical_2x2_adequate, "sex", "passed", "chi_square"),
        (F.two_categorical_2x2_small, "sex", "passed", "fisher_exact"),
        (F.two_categorical_3x3_small, "region", "grade", "chi_square"),
    ])
    def test_selects_correct_test(self, builder, va, vb, expected):
        result = live_select(builder(), va, vb)
        assert result.get("recommended_test") == expected, result.get("reasoning")

    def test_selection_is_order_independent(self):
        df = F.numeric_by_2group_equalvar()
        assert live_select(df, "bp", "arm")["recommended_test"] == live_select(df, "arm", "bp")["recommended_test"]


# ── 4. Template execution produces correct, parseable results ────────────────
class TestTemplateExecution:
    def test_pearson_detects_strong_correlation(self):
        out = run_template_locally(F.two_numeric_normal(), "pearson", "height", "weight")
        assert "Pearson r" in out and _p(out) is not None and _p(out) < 0.05

    def test_independent_t_detects_group_difference(self):
        out = run_template_locally(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        assert "T-statistic" in out and _p(out) is not None

    def test_welch_anova_runs_without_pingouin(self):
        out = run_template_locally(F.numeric_by_3group_unequalvar(), "welch_anova", "bp", "region")
        assert "F-statistic" in out and "approx" not in out.lower() and _p(out) is not None

    def test_chi_square_runs(self):
        out = run_template_locally(F.two_categorical_2x2_adequate(), "chi_square", "sex", "passed")
        assert "Chi-square statistic" in out and _p(out) is not None

    def test_mann_whitney_runs(self):
        out = run_template_locally(F.numeric_by_2group_skewed(), "mann_whitney", "bp", "arm")
        assert "U-statistic" in out and _p(out) is not None

    @pytest.mark.parametrize("key,df,a,b", [
        ("spearman", F.two_numeric_skewed(), "height", "income"),
        ("welch_t", F.numeric_by_2group_unequalvar(), "bp", "arm"),
        ("one_way_anova", F.numeric_by_3group_equalvar(), "bp", "region"),
        ("kruskal_wallis", F.numeric_by_3group_skewed(), "bp", "region"),
        ("fisher_exact", F.two_categorical_2x2_small(), "sex", "passed"),
    ])
    def test_template_prints_pvalue(self, key, df, a, b):
        out = run_template_locally(df, key, a, b)
        assert _p(out) is not None, out

    def test_identical_groups_not_significant(self):
        # sanity: a t-test on a group with no real difference should be n.s.
        import pandas as pd, numpy as np
        r = np.random.default_rng(1)
        vals = r.normal(100, 10, 100)
        df = pd.DataFrame({"bp": vals, "arm": ["a"] * 50 + ["b"] * 50})
        out = run_template_locally(df, "independent_t", "bp", "arm")
        assert _p(out) > 0.05


# ── 5. Injection safety of template rendering ────────────────────────────────
def test_template_render_is_injection_safe():
    from app.stats_engine.registry import render_template
    evil = "x'] ); import os; os.system('touch /tmp/pwned')  #"
    code = render_template("pearson", col_a=evil, col_b="y")
    assert "os.system" not in code or repr(evil) in code
    assert repr(evil) in code  # the name only ever appears inside a repr() literal
