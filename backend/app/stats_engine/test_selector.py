from typing import Any
from app.stats_engine.registry import get_test, get_all_test_names
from app.stats_engine.variable_classifier import (
    classify_variable, get_group_count, is_suitable_for_analysis,
    NUMERIC, NUMERIC_OR_ORDINAL, CATEGORICAL, IDENTIFIER, FREE_TEXT, UNKNOWN,
)
from app.stats_engine.assumption_checks import run_all_checks, PASS, FAIL, NOT_APPLICABLE

MULTIVARIATE_KEYWORDS = [
    "controlling for", "adjusting for", "after accounting for", "while controlling",
    "multivariate", "multiple regression", "multiple predictors", "logistic regression",
    "linear regression", "mixed model", "covariates",
]


def is_multivariate_request(user_message: str) -> bool:
    message_lower = user_message.lower()
    return any(kw in message_lower for kw in MULTIVARIATE_KEYWORDS)


def select_test(var_a: str, var_b: str, profile: dict[str, Any]) -> dict[str, Any]:
    suitable_a, reason_a = is_suitable_for_analysis(var_a, profile)
    suitable_b, reason_b = is_suitable_for_analysis(var_b, profile)

    if not suitable_a:
        return _clarification_result(reason_a, [var_a, var_b])
    if not suitable_b:
        return _clarification_result(reason_b, [var_a, var_b])

    type_a = classify_variable(var_a, profile)
    type_b = classify_variable(var_b, profile)

    if type_a == CATEGORICAL and type_b in [NUMERIC, NUMERIC_OR_ORDINAL]:
        var_a, var_b = var_b, var_a
        type_a, type_b = type_b, type_a

    group_count = 0
    if type_b == CATEGORICAL:
        group_count = get_group_count(var_b, profile)
    elif type_a == CATEGORICAL:
        group_count = get_group_count(var_a, profile)

    checks = run_all_checks(var_a, var_b, type_a, type_b, profile, group_count)

    if type_a in [NUMERIC, NUMERIC_OR_ORDINAL] and type_b in [NUMERIC, NUMERIC_OR_ORDINAL]:
        return _correlation_branch(var_a, var_b, type_a, type_b, checks)

    if type_a in [NUMERIC, NUMERIC_OR_ORDINAL] and type_b == CATEGORICAL:
        if group_count == 2:
            return _two_group_branch(var_a, var_b, checks, group_count)
        elif group_count >= 3:
            return _multi_group_branch(var_a, var_b, checks, group_count)
        else:
            return _clarification_result(f"'{var_b}' has {group_count} groups. A statistical comparison needs at least 2.", [var_a, var_b])

    if type_a == CATEGORICAL and type_b == CATEGORICAL:
        return _categorical_branch(var_a, var_b, checks)

    return _clarification_result(f"Could not determine the right test for '{var_a}' ({type_a}) and '{var_b}' ({type_b}).", [var_a, var_b])


def _correlation_branch(var_a, var_b, type_a, type_b, checks):
    both_normal = checks.get("normality_outcome") == PASS and checks.get("normality_b", PASS) == PASS
    if both_normal and type_a == NUMERIC and type_b == NUMERIC:
        return _result("pearson", ["spearman"], f"Both '{var_a}' and '{var_b}' are numeric and approximately normally distributed, so Pearson correlation is appropriate.", checks, [var_a, var_b], None)
    else:
        reason_parts = []
        if type_a == NUMERIC_OR_ORDINAL or type_b == NUMERIC_OR_ORDINAL:
            reason_parts.append("one or both variables are ordinal")
        if checks.get("normality_outcome") == FAIL:
            reason_parts.append(f"'{var_a}' is not normally distributed")
        if checks.get("normality_b") == FAIL:
            reason_parts.append(f"'{var_b}' is not normally distributed")
        reason = "Spearman rank correlation is appropriate because " + " and ".join(reason_parts) + "."
        return _result("spearman", ["pearson"], reason, checks, [var_a, var_b], None)


def _two_group_branch(outcome, grouping, checks, group_count):
    normality = checks.get("normality_outcome")
    variance = checks.get("variance_equal")
    sample_ok = checks.get("sample_size_ok")

    if normality == FAIL or sample_ok == FAIL:
        parts = []
        if normality == FAIL:
            parts.append(f"'{outcome}' is not normally distributed")
        if sample_ok == FAIL:
            parts.append("the group sizes are small")
        return _result("mann_whitney", ["independent_t"], "Mann-Whitney U is used because " + " and ".join(parts) + ".", checks, [outcome, grouping], group_count)

    if variance == FAIL:
        return _result("welch_t", ["independent_t", "mann_whitney"], f"Welch's t-test is used because '{outcome}' is normally distributed but group variances appear unequal.", checks, [outcome, grouping], group_count)

    return _result("independent_t", ["welch_t", "mann_whitney"], f"Independent samples t-test is appropriate: '{outcome}' is normally distributed, group variances are similar, and sample size is adequate.", checks, [outcome, grouping], group_count)


def _multi_group_branch(outcome, grouping, checks, group_count):
    normality = checks.get("normality_outcome")
    variance = checks.get("variance_equal")
    sample_ok = checks.get("sample_size_ok")

    if normality == FAIL or sample_ok == FAIL:
        parts = []
        if normality == FAIL:
            parts.append(f"'{outcome}' is not normally distributed")
        if sample_ok == FAIL:
            parts.append("group sizes are small")
        return _result("kruskal_wallis", ["one_way_anova"], f"Kruskal-Wallis is used because " + " and ".join(parts) + f". With {group_count} groups, post-hoc Dunn's test will identify which groups differ if significant.", checks, [outcome, grouping], group_count)

    if variance == FAIL:
        return _result("welch_anova", ["one_way_anova", "kruskal_wallis"], f"Welch's ANOVA is used because '{outcome}' is normally distributed but group variances appear unequal across {group_count} groups.", checks, [outcome, grouping], group_count)

    return _result("one_way_anova", ["welch_anova", "kruskal_wallis"], f"One-way ANOVA is appropriate: '{outcome}' is normally distributed, variances are similar, and sample size is adequate across {group_count} groups.", checks, [outcome, grouping], group_count)


def _categorical_branch(var_a, var_b, checks):
    expected_cells_ok = checks.get("min_expected_cell")
    if expected_cells_ok == FAIL:
        return _result("fisher_exact", ["chi_square"], f"Fisher's exact test is used because expected cell counts are too small for chi-square.", checks, [var_a, var_b], None)
    return _result("chi_square", ["fisher_exact"], f"Chi-square test of independence is appropriate: both '{var_a}' and '{var_b}' are categorical and expected cell counts are adequate.", checks, [var_a, var_b], None)


def _result(recommended, alternates, reasoning, checks, variables, group_count):
    return {
        "recommended_test": recommended, "alternates": alternates, "reasoning": reasoning,
        "assumption_results": checks, "variables": variables, "group_count": group_count,
        "multivariate": False, "unsupported": False, "needs_clarification": False, "clarification_reason": None,
    }


def _clarification_result(reason, variables):
    return {
        "recommended_test": None, "alternates": [], "reasoning": reason,
        "assumption_results": {}, "variables": variables, "group_count": None,
        "multivariate": False, "unsupported": False, "needs_clarification": True, "clarification_reason": reason,
    }


def explain_test_choice(result: dict[str, Any]) -> str:
    return result.get("reasoning", "")


def get_multivariate_fallback_message(variables: list[str]) -> str:
    var_list = " and ".join(f"'{v}'" for v in variables)
    return (
        f"It looks like you want to examine multiple variables ({var_list}) together — "
        f"that's a multivariate analysis (like multiple regression), which I don't support yet.\n\n"
        f"What I can do right now: run a bivariate test on any two of those variables at a time. "
        f"Which two would you like to start with?"
    )
