import json
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


# ── Live, per-group assumption checks ─────────────────────────────────────────
# The functions above read the STATIC upload-time profile and check the POOLED
# column, which is the wrong question for grouped comparisons (a column can look
# skewed overall purely because of the grouping) and goes stale if the data is
# later cleaned/filtered. The live path below runs real per-group tests
# (Shapiro/D'Agostino normality, Levene/Brown-Forsythe variance, live expected
# cell counts) on the CURRENT data in the sandbox. It returns the exact same
# PASS/FAIL/NOT_APPLICABLE vocabulary and keys, so the test-selector decision
# tree consumes it unchanged.

_NUMERICISH = ("numeric", "numeric_or_ordinal")


def _build_check_script(scenario: str, col_a: str, col_b: str, min_n: int, min_cell: int) -> str:
    """col_a/col_b are inserted via repr() so a hostile column name can't break
    out of the string literal. scenario is one of: num_num, num_cat, cat_cat."""
    a, b = repr(col_a), repr(col_b)
    header = f"""
import json
import numpy as np
import pandas as pd
from scipy import stats

PASS, FAIL, NA = "pass", "fail", "not_applicable"
df = pd.read_csv('/home/user/data.csv')
result = {{}}

def _normal(series):
    s = series.dropna()
    n = len(s)
    if n < 3 or s.nunique() < 3:
        return NA
    try:
        if n >= 20:
            _, p = stats.normaltest(s)
        else:
            _, p = stats.shapiro(s)
    except Exception:
        return NA
    # Use alpha = 0.01 (not 0.05) for the normality PRE-test. Normality tests
    # over-reject genuinely-normal data (~3.5% at 0.05 here) and t-tests/ANOVA
    # are robust to MILD non-normality, so we only switch to a non-parametric
    # test on STRONG evidence of non-normality. Skewed data still fails easily.
    return PASS if p >= 0.01 else FAIL
"""
    if scenario == "num_num":
        body = f"""
result["normality_outcome"] = _normal(df[{a}])
result["normality_b"] = _normal(df[{b}])
result["variance_equal"] = NA
result["sample_size_ok"] = PASS if df[[{a}, {b}]].dropna().shape[0] >= {min_n} else FAIL
result["min_expected_cell"] = NA
"""
    elif scenario == "num_cat":
        body = f"""
groups = [g[{a}].dropna() for _, g in df.groupby({b}) if g[{a}].dropna().shape[0] > 1]
# Normality (t-tests/ANOVA) is about the within-group residuals. Test the
# pooled, group-STANDARDIZED residuals ((x - group_mean) / group_sd) once:
#  - one test avoids the multiple-comparison inflation of testing each group;
#  - standardizing decouples normality from variance, so unequal group variances
#    don't spuriously fail normality (raw pooled residuals from unequal-variance
#    groups are a non-normal mixture).
_std = [g.std(ddof=1) for g in groups]
if len(groups) >= 2 and all(s and s > 0 for s in _std):
    resid = np.concatenate([(g.values - g.mean()) / s for g, s in zip(groups, _std)])
    result["normality_outcome"] = _normal(pd.Series(resid)) if len(resid) >= 3 else NA
else:
    result["normality_outcome"] = NA
result["normality_b"] = NA
if len(groups) >= 2:
    try:
        _, lp = stats.levene(*groups, center='median')
        result["variance_equal"] = PASS if lp >= 0.05 else FAIL
    except Exception:
        result["variance_equal"] = NA
else:
    result["variance_equal"] = NA
sizes = [len(g) for g in groups]
result["sample_size_ok"] = PASS if sizes and min(sizes) >= {min_n} else FAIL
result["min_expected_cell"] = NA
"""
    else:  # cat_cat
        body = f"""
result["normality_outcome"] = NA
result["normality_b"] = NA
result["variance_equal"] = NA
result["sample_size_ok"] = PASS if df[[{a}, {b}]].dropna().shape[0] >= {min_n} else FAIL
try:
    contingency = pd.crosstab(df[{a}], df[{b}])
    _, _, _, expected = stats.chi2_contingency(contingency)
    result["min_expected_cell"] = PASS if expected.min() >= {min_cell} else FAIL
except Exception:
    result["min_expected_cell"] = NA
"""
    return header + body + "\nprint(json.dumps(result))\n"


def select_scenario(type_a: str, type_b: str) -> str | None:
    """Which live-check scenario applies to this typed pair (or None if the
    combination has no verified assumption checks)."""
    if type_a in _NUMERICISH and type_b in _NUMERICISH:
        return "num_num"
    if type_a in _NUMERICISH and type_b == "categorical":
        return "num_cat"
    if type_a == "categorical" and type_b == "categorical":
        return "cat_cat"
    return None


def build_check_script_for(var_a: str, var_b: str, type_a: str, type_b: str) -> str | None:
    """The full live-check script for a typed pair, or None if unsupported.
    Split out so tests can run it locally (no E2B) against the same code path."""
    scenario = select_scenario(type_a, type_b)
    if scenario is None:
        return None
    return _build_check_script(scenario, var_a, var_b, MIN_SAMPLE_SIZE_PER_GROUP, CHI_SQUARE_MIN_EXPECTED_CELL)


def parse_checks(stdout: str | None) -> dict[str, str]:
    """Parse the JSON the check script prints into the PASS/FAIL/NA dict, keeping
    only known keys with a valid vocabulary. Falls back to all-NA on any problem,
    so the decision tree still runs (treating unknown assumptions as unmet-safe)."""
    out = _blank_checks()
    text = (stdout or "").strip()
    if not text:
        return out
    try:
        parsed = json.loads(text.splitlines()[-1])
    except (json.JSONDecodeError, ValueError, IndexError):
        return out
    for key in out:
        val = parsed.get(key)
        if val in (PASS, FAIL, NOT_APPLICABLE):
            out[key] = val
    return out


async def run_live_checks(sbx, var_a: str, var_b: str, type_a: str, type_b: str) -> dict[str, str]:
    """Run assumption checks on the live data. Expects var_a/var_b already
    normalized by the caller so that for a group comparison var_a is the numeric
    OUTCOME and var_b is the categorical GROUPING variable."""
    from app.sandbox.executor import execute_code  # local import avoids a cycle

    script = build_check_script_for(var_a, var_b, type_a, type_b)
    if script is None:
        return _blank_checks()
    exec_result = await execute_code(sbx, script)
    return parse_checks(exec_result.get("stdout"))


def _blank_checks() -> dict[str, str]:
    return {
        "normality_outcome": NOT_APPLICABLE,
        "normality_b": NOT_APPLICABLE,
        "variance_equal": NOT_APPLICABLE,
        "sample_size_ok": NOT_APPLICABLE,
        "min_expected_cell": NOT_APPLICABLE,
    }
