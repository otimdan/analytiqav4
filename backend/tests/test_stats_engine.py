# Run with: pytest tests/test_stats_engine.py -v
# Zero API keys, zero E2B, zero network required.

import pytest
from app.stats_engine.variable_classifier import (
    classify_variable, classify_pair, get_group_count, is_suitable_for_analysis,
    NUMERIC, NUMERIC_OR_ORDINAL, CATEGORICAL, IDENTIFIER, FREE_TEXT, UNKNOWN,
)
from app.stats_engine.assumption_checks import (
    check_normality, check_variance_homogeneity, check_sample_size,
    check_expected_cell_count, run_all_checks, PASS, FAIL, NOT_APPLICABLE,
)
from app.stats_engine.test_selector import (
    select_test, is_multivariate_request, get_multivariate_fallback_message,
)


def _make_profile(row_count: int = 200, **columns) -> dict:
    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": {
            name: {
                "pandas_dtype": "float64", "null_count": 0, "null_pct": 0,
                "unique_count": row_count, "uniqueness_ratio": 1.0,
                "mean": 50.0, "median": 50.0, "std": 10.0, "min": 10.0, "max": 90.0,
                "q25": 40.0, "q75": 60.0, "skewness": 0.1,
                "likely_categorical": False, "likely_datetime": False,
                "semantic_guess": "numeric_measurement",
                **col_data,
            }
            for name, col_data in columns.items()
        },
    }


def _numeric_col(skewness=0.1, null_pct=0):
    return {"pandas_dtype": "float64", "skewness": skewness, "null_pct": null_pct, "null_count": 0,
            "unique_count": 150, "uniqueness_ratio": 0.75, "likely_categorical": False, "semantic_guess": "numeric_measurement"}


def _categorical_col(n_groups=2, null_pct=0, dtype="object"):
    return {"pandas_dtype": dtype, "null_pct": null_pct, "unique_count": n_groups,
            "uniqueness_ratio": n_groups / 200, "group_count": n_groups,
            "likely_categorical": False, "likely_datetime": False, "semantic_guess": "categorical_grouping"}


def _ordinal_col(skewness=0.5):
    return {"pandas_dtype": "int64", "skewness": skewness, "null_pct": 0, "unique_count": 5,
            "uniqueness_ratio": 0.025, "likely_categorical": False, "semantic_guess": "ordinal_scale"}


def _id_col():
    return {"pandas_dtype": "int64", "unique_count": 200, "uniqueness_ratio": 1.0,
            "null_pct": 0, "semantic_guess": "identifier"}


class TestVariableClassifier:
    def test_numeric_column(self):
        profile = _make_profile(age=_numeric_col())
        assert classify_variable("age", profile) == NUMERIC

    def test_categorical_object_column(self):
        profile = _make_profile(group=_categorical_col())
        assert classify_variable("group", profile) == CATEGORICAL

    def test_ordinal_column(self):
        profile = _make_profile(severity=_ordinal_col())
        assert classify_variable("severity", profile) == NUMERIC_OR_ORDINAL

    def test_identifier_column(self):
        profile = _make_profile(patient_id=_id_col())
        assert classify_variable("patient_id", profile) == IDENTIFIER

    def test_numerically_coded_categorical(self):
        profile = _make_profile(intervention={"pandas_dtype": "int64", "unique_count": 2,
            "uniqueness_ratio": 0.01, "null_pct": 0.0, "likely_categorical": True,
            "group_count": 2, "semantic_guess": "categorical_grouping"})
        assert classify_variable("intervention", profile) == CATEGORICAL

    def test_high_missingness_unsuitable(self):
        profile = _make_profile(sparse={**_numeric_col(), "null_pct": 85.0})
        suitable, reason = is_suitable_for_analysis("sparse", profile)
        assert suitable is False
        assert "missing" in reason.lower()

    def test_classify_pair_puts_numeric_first(self):
        profile = _make_profile(severity=_numeric_col(), group=_categorical_col(n_groups=2))
        type_a, type_b = classify_pair("group", "severity", profile)
        assert type_a in [NUMERIC, NUMERIC_OR_ORDINAL]
        assert type_b == CATEGORICAL


class TestAssumptionChecks:
    def test_normality_passes_low_skewness(self):
        profile = _make_profile(score=_numeric_col(skewness=0.3))
        assert check_normality("score", profile) == PASS

    def test_normality_fails_high_skewness(self):
        profile = _make_profile(score=_numeric_col(skewness=2.5))
        assert check_normality("score", profile) == FAIL

    def test_normality_not_applicable_categorical(self):
        profile = _make_profile(group=_categorical_col())
        assert check_normality("group", profile) == NOT_APPLICABLE

    def test_sample_size_passes_adequate(self):
        profile = _make_profile(row_count=200, group=_categorical_col(n_groups=2))
        assert check_sample_size("group", profile, n_groups=2) == PASS

    def test_sample_size_fails_small(self):
        profile = _make_profile(row_count=30, group=_categorical_col(n_groups=4))
        assert check_sample_size("group", profile, n_groups=4) == FAIL

    def test_expected_cell_passes_large_sample(self):
        profile = _make_profile(row_count=200, var_a=_categorical_col(n_groups=2), var_b=_categorical_col(n_groups=2))
        assert check_expected_cell_count("var_a", "var_b", profile) == PASS

    def test_expected_cell_fails_small_sample(self):
        profile = _make_profile(row_count=20, var_a=_categorical_col(n_groups=4), var_b=_categorical_col(n_groups=3))
        assert check_expected_cell_count("var_a", "var_b", profile) == FAIL


class TestTestSelector:
    def test_pearson_two_normal_numerics(self):
        profile = _make_profile(row_count=200, age=_numeric_col(skewness=0.2), bp=_numeric_col(skewness=0.3))
        result = select_test("age", "bp", profile)
        assert result["recommended_test"] == "pearson"

    def test_spearman_non_normal(self):
        profile = _make_profile(row_count=200, age=_numeric_col(skewness=0.2), income=_numeric_col(skewness=2.8))
        result = select_test("age", "income", profile)
        assert result["recommended_test"] == "spearman"

    def test_spearman_ordinal(self):
        profile = _make_profile(row_count=200, severity=_ordinal_col(skewness=0.2), age=_numeric_col(skewness=0.1))
        result = select_test("severity", "age", profile)
        assert result["recommended_test"] == "spearman"

    def test_t_test_normal_two_groups(self):
        profile = _make_profile(row_count=200, score=_numeric_col(skewness=0.3), group={**_categorical_col(n_groups=2), "group_count": 2})
        result = select_test("score", "group", profile)
        assert result["recommended_test"] == "independent_t"

    def test_mann_whitney_non_normal_two_groups(self):
        profile = _make_profile(row_count=200, severity=_numeric_col(skewness=2.1), intervention={**_categorical_col(n_groups=2), "group_count": 2})
        result = select_test("severity", "intervention", profile)
        assert result["recommended_test"] == "mann_whitney"

    def test_anova_three_groups(self):
        profile = _make_profile(row_count=300, score=_numeric_col(skewness=0.2), village={**_categorical_col(n_groups=3), "group_count": 3})
        result = select_test("score", "village", profile)
        assert result["recommended_test"] == "one_way_anova"

    def test_kruskal_non_normal_three_groups(self):
        profile = _make_profile(row_count=300, severity=_numeric_col(skewness=1.8), village={**_categorical_col(n_groups=4), "group_count": 4})
        result = select_test("severity", "village", profile)
        assert result["recommended_test"] == "kruskal_wallis"

    def test_chi_square_categorical(self):
        profile = _make_profile(row_count=200, sex=_categorical_col(n_groups=2), outcome=_categorical_col(n_groups=2))
        result = select_test("sex", "outcome", profile)
        assert result["recommended_test"] == "chi_square"

    def test_fisher_two_by_two_small_cells(self):
        # Genuine 2x2 with small expected cells -> Fisher's exact (which the
        # template supports only for 2x2).
        profile = _make_profile(row_count=16, sex=_categorical_col(n_groups=2), outcome=_categorical_col(n_groups=2))
        result = select_test("sex", "outcome", profile)
        assert result["recommended_test"] == "fisher_exact"

    def test_large_sparse_categorical_uses_chi_square(self):
        # A >2x2 table with small cells CANNOT use the Fisher template (2x2 only),
        # so the engine falls back to chi-square with a small-cells caveat.
        profile = _make_profile(row_count=20, sex=_categorical_col(n_groups=4), outcome=_categorical_col(n_groups=3))
        result = select_test("sex", "outcome", profile)
        assert result["recommended_test"] == "chi_square"
        assert "caution" in result["reasoning"].lower() or "small" in result["reasoning"].lower()

    def test_identifier_triggers_clarification(self):
        profile = _make_profile(row_count=200, patient_id=_id_col(), score=_numeric_col())
        result = select_test("patient_id", "score", profile)
        assert result["needs_clarification"] is True

    def test_variable_order_independent(self):
        profile = _make_profile(row_count=200, score=_numeric_col(skewness=0.3), group={**_categorical_col(n_groups=2), "group_count": 2})
        result_a = select_test("score", "group", profile)
        result_b = select_test("group", "score", profile)
        assert result_a["recommended_test"] == result_b["recommended_test"]

    def test_result_always_has_reasoning(self):
        profile = _make_profile(row_count=200, score=_numeric_col(skewness=0.2), group={**_categorical_col(n_groups=2), "group_count": 2})
        result = select_test("score", "group", profile)
        assert isinstance(result["reasoning"], str) and len(result["reasoning"]) > 20

    def test_alternates_never_contains_recommended(self):
        profile = _make_profile(row_count=200, score=_numeric_col(skewness=2.5), group={**_categorical_col(n_groups=2), "group_count": 2})
        result = select_test("score", "group", profile)
        assert result["recommended_test"] not in result["alternates"]

    def test_multivariate_detected(self):
        assert is_multivariate_request("does intervention predict recovery controlling for age?") is True

    def test_bivariate_not_multivariate(self):
        assert is_multivariate_request("is severity different between groups?") is False

    def test_multivariate_fallback_names_variables(self):
        msg = get_multivariate_fallback_message(["age", "severity", "intervention"])
        assert "age" in msg and "severity" in msg


class TestRegressionCases:
    def test_int_zero_one_is_categorical(self):
        profile = _make_profile(row_count=200, symptom_severity=_numeric_col(skewness=0.5),
            intervention_group={"pandas_dtype": "int64", "unique_count": 2, "uniqueness_ratio": 0.01,
                "null_pct": 0.0, "skewness": 0.0, "likely_categorical": True, "group_count": 2, "semantic_guess": "categorical_grouping"})
        t = classify_variable("intervention_group", profile)
        assert t == CATEGORICAL
        result = select_test("symptom_severity", "intervention_group", profile)
        assert result["recommended_test"] != "pearson"

    def test_empty_profile_no_crash(self):
        empty = {"row_count": 0, "column_count": 0, "columns": {}}
        result = select_test("a", "b", empty)
        assert result["needs_clarification"] is True

    def test_single_group_no_crash(self):
        profile = _make_profile(row_count=200, score=_numeric_col(), group={**_categorical_col(n_groups=1), "group_count": 1})
        result = select_test("score", "group", profile)
        assert result["needs_clarification"] is True
