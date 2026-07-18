import difflib
import re
from typing import Any, Optional
from app.stats_engine.registry import get_test, get_all_test_names, SUPPORTED_TESTS
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


def resolve_pair(var_a: str, var_b: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, profile-only first half of test selection: validate the two
    columns, classify their types, normalize their order (numeric OUTCOME first,
    categorical GROUPING second), and count groups. Returns either an error
    result (needs_clarification / unsupported) or {"ok": True, ...resolved...}.

    Split out from `select_test` so the caller can run LIVE assumption checks on
    the resolved pair before handing them to `decide_test`."""
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

    numericish = [NUMERIC, NUMERIC_OR_ORDINAL]
    is_supported = (
        (type_a in numericish and type_b in numericish)
        or (type_a in numericish and type_b == CATEGORICAL)
        or (type_a == CATEGORICAL and type_b == CATEGORICAL)
    )
    if not is_supported:
        return _unsupported_result(
            f"There's no verified test in the library for comparing '{var_a}' ({type_a}) "
            f"and '{var_b}' ({type_b}).",
            [var_a, var_b],
        )

    group_count = 0
    if type_b == CATEGORICAL:
        group_count = get_group_count(var_b, profile)
    elif type_a == CATEGORICAL:
        group_count = get_group_count(var_a, profile)

    if type_a in numericish and type_b == CATEGORICAL and group_count < 2:
        return _clarification_result(f"'{var_b}' has {group_count} group(s). A statistical comparison needs at least 2.", [var_a, var_b])

    # Cardinalities of each categorical column — used to tell a genuine 2x2 table
    # (Fisher-eligible) from a larger one (where Fisher's template doesn't apply).
    card_a = get_group_count(var_a, profile) if type_a == CATEGORICAL else None
    card_b = get_group_count(var_b, profile) if type_b == CATEGORICAL else None

    return {"ok": True, "var_a": var_a, "var_b": var_b, "type_a": type_a, "type_b": type_b, "group_count": group_count, "card_a": card_a, "card_b": card_b}


def decide_test(resolved: dict[str, Any], checks: dict[str, str]) -> dict[str, Any]:
    """Deterministic second half: given a resolved pair and assumption-check
    results (live or static), walk the decision tree to a recommended test."""
    var_a, var_b = resolved["var_a"], resolved["var_b"]
    type_a, type_b = resolved["type_a"], resolved["type_b"]
    group_count = resolved["group_count"]
    numericish = [NUMERIC, NUMERIC_OR_ORDINAL]

    if type_a in numericish and type_b in numericish:
        return _correlation_branch(var_a, var_b, type_a, type_b, checks)
    if type_a in numericish and type_b == CATEGORICAL:
        if group_count == 2:
            return _two_group_branch(var_a, var_b, checks, group_count)
        return _multi_group_branch(var_a, var_b, checks, group_count)
    if type_a == CATEGORICAL and type_b == CATEGORICAL:
        return _categorical_branch(var_a, var_b, checks, resolved.get("card_a"), resolved.get("card_b"))
    return _unsupported_result(f"There's no verified test for '{var_a}' ({type_a}) and '{var_b}' ({type_b}).", [var_a, var_b])


def select_test(var_a: str, var_b: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Convenience path using STATIC (profile-derived) assumption checks. The
    confirmatory handler uses resolve_pair + live checks + decide_test instead;
    this remains for callers that only have the profile."""
    resolved = resolve_pair(var_a, var_b, profile)
    if not resolved.get("ok"):
        return resolved
    checks = run_all_checks(resolved["var_a"], resolved["var_b"], resolved["type_a"], resolved["type_b"], profile, resolved["group_count"])
    return decide_test(resolved, checks)


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


def _categorical_branch(var_a, var_b, checks, card_a=None, card_b=None):
    expected_cells_ok = checks.get("min_expected_cell")
    is_two_by_two = card_a == 2 and card_b == 2
    if expected_cells_ok == FAIL:
        if is_two_by_two:
            return _result("fisher_exact", ["chi_square"], "Fisher's exact test is used because expected cell counts are too small for chi-square (and the table is 2x2).", checks, [var_a, var_b], None)
        # Fisher's here only supports 2x2, so for a larger table with small cells
        # we still use chi-square (the best verified option) and flag the caveat.
        return _result("chi_square", ["fisher_exact"], f"Chi-square test of independence is used for '{var_a}' vs '{var_b}'. Note: some expected cell counts are small, so treat the p-value with caution (an exact test would be preferable for a table this size).", checks, [var_a, var_b], None)
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
        "ok": False,
    }


def _unsupported_result(reason, variables):
    """Distinct from needs_clarification: the data is fine, but the registry has
    no verified test for this combination. The caller routes these to the
    LLM-assisted (engine_verified=false) tier rather than asking the user to pick
    different columns."""
    return {
        "recommended_test": None, "alternates": [], "reasoning": reason,
        "assumption_results": {}, "variables": variables, "group_count": None,
        "multivariate": False, "unsupported": True, "needs_clarification": False, "clarification_reason": reason,
        "ok": False,
    }


# ── Fuzzy resolution of a user-named test ─────────────────────────────────────
# Common aliases/synonyms mapped to canonical registry names. The candidate pool
# is built from the registry itself (test_name + display_name) so it can't drift
# out of sync with what's actually supported.
_TEST_SYNONYMS: dict[str, str] = {
    "t test": "independent_t", "ttest": "independent_t", "t-test": "independent_t",
    "student t": "independent_t", "independent t": "independent_t",
    "welch": "welch_t", "welch t": "welch_t", "welchs t": "welch_t",
    "welch anova": "welch_anova",
    "anova": "one_way_anova", "one way anova": "one_way_anova", "f test": "one_way_anova",
    "mann whitney": "mann_whitney", "mannwhitney": "mann_whitney", "wilcoxon rank sum": "mann_whitney",
    "u test": "mann_whitney",
    "kruskal": "kruskal_wallis", "kruskal wallis": "kruskal_wallis",
    "chi square": "chi_square", "chi squared": "chi_square", "chisquare": "chi_square",
    "chi2": "chi_square", "chi-square": "chi_square",
    "fisher": "fisher_exact", "fishers exact": "fisher_exact", "fisher exact": "fisher_exact",
    "pearson": "pearson", "pearson correlation": "pearson",
    "spearman": "spearman", "spearman correlation": "spearman", "rank correlation": "spearman",
}
# NOTE: the bare word "correlation" is deliberately NOT mapped — it's generic
# (could be Pearson or Spearman), so it must NOT override the engine's
# assumption-based choice. Only a specific name ("pearson"/"spearman") overrides.


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def resolve_requested_test(message: str) -> tuple[Optional[str], bool]:
    """Detect which registry test (if any) the user explicitly asked for, tolerant
    of typos and phrasing. Returns (test_name, high_confidence).
      - (name, True):  confident match  -> honor it as an override, run verified.
      - (name, False): a plausible-but-uncertain near-match -> caller may confirm.
      - (None, False): no test-shaped request -> use the recommended test.
    """
    norm = _normalize(message)
    if not norm:
        return None, False

    # 1. Direct synonym substring hit — highest confidence. Check longer aliases
    # first so "welch anova" wins over the shorter "welch".
    for alias in sorted(_TEST_SYNONYMS, key=len, reverse=True):
        if alias in norm:
            return _TEST_SYNONYMS[alias], True

    # 2. Fuzzy match of message tokens/windows against canonical names + aliases.
    candidates: dict[str, str] = {}  # phrase -> canonical
    for t in SUPPORTED_TESTS:
        candidates[_normalize(t["test_name"].replace("_", " "))] = t["test_name"]
        candidates[_normalize(t["display_name"])] = t["test_name"]
    for alias, canonical in _TEST_SYNONYMS.items():
        candidates[alias] = canonical

    words = norm.split()
    windows = set(words)
    for i in range(len(words) - 1):
        windows.add(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        windows.add(f"{words[i]} {words[i+1]} {words[i+2]}")

    best_name: Optional[str] = None
    best_score = 0.0
    for window in windows:
        match = difflib.get_close_matches(window, candidates.keys(), n=1, cutoff=0.82)
        if match:
            score = difflib.SequenceMatcher(None, window, match[0]).ratio()
            if score > best_score:
                best_score, best_name = score, candidates[match[0]]

    if best_name is None:
        return None, False
    return best_name, best_score >= 0.9


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
