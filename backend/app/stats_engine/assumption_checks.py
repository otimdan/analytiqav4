from typing import Any
from app.config import MIN_SAMPLE_SIZE_PER_GROUP, CHI_SQUARE_MIN_EXPECTED_CELL
from app.profiling.profiler import get_column_profile
from app.stats_engine.variable_classifier import classify_variable, NUMERIC, NUMERIC_OR_ORDINAL

PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"


def check_normality(column_name: str, profile: dict[str, Any]) -> str:
    col = get_column_profile(profile, column_name)
    if not col:
        return NOT_APPLICABLE
    if classify_variable(column_name, profile) not in (NUMERIC, NUMERIC_OR_ORDINAL):
        return NOT_APPLICABLE
    skewness = col.get("skewness")
    if skewness is None:
        return NOT_APPLICABLE
    return PASS if abs(skewness) <= 1.0 else FAIL


def check_variance_homogeneity(outcome_column: str, grouping_column: str, profile: dict[str, Any]) -> str:
    outcome = get_column_profile(profile, outcome_column)
    if not outcome:
        return NOT_APPLICABLE
    overall_std = outcome.get("std")
    if overall_std is None:
        return NOT_APPLICABLE
    mean = outcome.get("mean", 0)
    if mean and mean != 0:
        cv = abs(overall_std / mean)
        return FAIL if cv > 1.0 else PASS
    return PASS


def check_sample_size(grouping_column: str, profile: dict[str, Any], n_groups: int = 2) -> str:
    col = get_column_profile(profile, grouping_column)
    if not col:
        return NOT_APPLICABLE
    total_rows = profile.get("row_count", 0)
    if total_rows == 0:
        return FAIL
    group_count = col.get("group_count") or col.get("unique_count", n_groups)
    if group_count == 0:
        return NOT_APPLICABLE
    estimated_per_group = total_rows / group_count
    return PASS if estimated_per_group >= MIN_SAMPLE_SIZE_PER_GROUP else FAIL


def check_expected_cell_count(var_a: str, var_b: str, profile: dict[str, Any]) -> str:
    col_a = get_column_profile(profile, var_a)
    col_b = get_column_profile(profile, var_b)
    if not col_a or not col_b:
        return NOT_APPLICABLE
    groups_a = col_a.get("group_count") or col_a.get("unique_count", 2)
    groups_b = col_b.get("group_count") or col_b.get("unique_count", 2)
    total_rows = profile.get("row_count", 0)
    if groups_a == 0 or groups_b == 0:
        return NOT_APPLICABLE
    expected_per_cell = total_rows / (groups_a * groups_b)
    return PASS if expected_per_cell >= CHI_SQUARE_MIN_EXPECTED_CELL else FAIL


def run_all_checks(
    var_a: str, var_b: str, type_a: str, type_b: str,
    profile: dict[str, Any], group_count: int,
) -> dict[str, str]:
    results: dict[str, str] = {}
    numeric_types = ["numeric", "numeric_or_ordinal"]
    categorical_types = ["categorical"]

    if type_a in numeric_types and type_b in numeric_types:
        results["normality_outcome"] = check_normality(var_a, profile)
        results["normality_b"] = check_normality(var_b, profile)
    elif type_a in numeric_types:
        results["normality_outcome"] = check_normality(var_a, profile)
    elif type_b in numeric_types:
        results["normality_outcome"] = check_normality(var_b, profile)
    else:
        results["normality_outcome"] = NOT_APPLICABLE

    if type_a in numeric_types and type_b in categorical_types:
        results["variance_equal"] = check_variance_homogeneity(var_a, var_b, profile)
    elif type_b in numeric_types and type_a in categorical_types:
        results["variance_equal"] = check_variance_homogeneity(var_b, var_a, profile)
    else:
        results["variance_equal"] = NOT_APPLICABLE

    grouping_var = var_b if type_a in numeric_types else var_a
    results["sample_size_ok"] = check_sample_size(grouping_var, profile, group_count)

    if type_a in categorical_types and type_b in categorical_types:
        results["min_expected_cell"] = check_expected_cell_count(var_a, var_b, profile)
    else:
        results["min_expected_cell"] = NOT_APPLICABLE

    return results
