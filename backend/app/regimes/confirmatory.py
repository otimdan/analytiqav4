import re
from typing import Any, Optional
from app.db.models import Session, Message
from app.llm.fireworks_client import call_main_model, call_structured_output
from app.llm.prompts import (
    NARRATION_SYSTEM_PROMPT, repair_prompt, ASSISTED_TEST_SYSTEM_PROMPT,
    REGRESSION_EXTRACTION_SYSTEM_PROMPT, REGRESSION_NARRATION_SYSTEM_PROMPT,
)
from app.llm.schemas import ConfirmatoryNarration, RegressionSpec
from app.sandbox.manager import get_or_create_sandbox
from app.sandbox.executor import execute_code
from app.sandbox.repair import attempt_repair
from app.stats_engine.test_selector import (
    resolve_pair, decide_test, resolve_requested_test,
    is_multivariate_request, get_multivariate_fallback_message, explain_test_choice,
)
from app.stats_engine.column_matcher import match_columns
from app.stats_engine.registry import get_test, render_template, render_posthoc, posthoc_label
from app.stats_engine.regression import resolve_model, render_regression
from app.stats_engine.assumption_checks import run_live_checks, PASS, FAIL, NOT_APPLICABLE
from app.reports.stats_extract import extract_test_stats
from app.profiling.cache import get_cached_profile
from app.db.artifacts import find_similar_artifact
from app.db.aio import run_db

# Explicit-request downgrades that re-introduce a failed variance assumption:
# the engine picked the Welch (unequal-variance) variant, so forcing the
# equal-variance counterpart the user named would be less accurate.
_VARIANCE_DOWNGRADES = {("welch_t", "independent_t"), ("welch_anova", "one_way_anova")}


def _is_assumption_downgrade(recommended_test: str, requested_test: str) -> bool:
    """True if honoring an explicit request for `requested_test` over the engine's
    `recommended_test` would re-introduce a violated assumption — i.e. swap the
    engine's assumption-appropriate choice for a less-valid one:
      - non-parametric recommended -> parametric requested (normality/sample failed)
      - Welch (variance-robust) recommended -> equal-variance counterpart requested
    In those cases accuracy wins and we keep the engine's choice."""
    rec, req = get_test(recommended_test), get_test(requested_test)
    if not rec or not req:
        return False
    nonparam_downgrade = bool(rec.get("nonparametric") and not req.get("nonparametric"))
    variance_downgrade = (recommended_test, requested_test) in _VARIANCE_DOWNGRADES
    return nonparam_downgrade or variance_downgrade


async def handle(message: str, session: Session, context: dict[str, Any], recent_messages: list[Message]) -> dict[str, Any]:
    mode = context.get("mode", "explore")
    profile = await run_db(get_cached_profile, str(session.id))
    if not profile:
        return _text_result("I need your dataset profile first. Try again in a moment.")

    # Regression / multivariable modelling → the verified regression path
    # (replaces the old "multivariate not supported" fallback).
    if _is_regression_request(message):
        return await _regression(message, session, context, profile, mode)

    variables, clarification = resolve_pair_variables(message, profile, context.get("focus_variables"))
    if clarification:
        return _text_result(clarification)

    var_a, var_b = variables[0], variables[1]
    resolved = resolve_pair(var_a, var_b, profile)

    if resolved.get("needs_clarification"):
        return _text_result(resolved.get("clarification_reason") or "I need more information to pick the right test.")

    # No verified test covers this combination -> honest LLM-assisted tier.
    if resolved.get("unsupported"):
        return await _assisted_run(message, session, context, [var_a, var_b], resolved.get("reasoning", ""))

    n_var_a, n_var_b = resolved["var_a"], resolved["var_b"]  # normalized order

    # A user explicitly asked for a specific, unsupported-by-registry test
    # (e.g. "paired t-test", "ANCOVA"): resolve_requested_test returns None for
    # those, so this only fires for registry tests. Low-confidence near-matches
    # fall through to the recommended test rather than guessing.
    requested_test, requested_confident = resolve_requested_test(message)

    # If we've already done assumption checks for this pair (guided pause on a
    # previous turn), reuse that decision and go straight to running the test.
    existing = await run_db(find_similar_artifact, session_id=str(session.id), stage="assumption_checks", artifact_type="assumption_check", variables_involved=[n_var_a, n_var_b])

    if existing:
        content = existing.content or {}
        recommended_test = content.get("recommended_test")
        reasoning = content.get("reasoning", "")
        checks = content.get("assumption_results", {})
        if not recommended_test:
            return await _run_verified_from_scratch(message, session, context, resolved, requested_test, requested_confident)
        return await _run_verified(session, context, n_var_a, n_var_b, recommended_test, reasoning, checks, requested_test, requested_confident)

    # First time on this pair. Run LIVE assumption checks on the current data.
    sbx = await get_or_create_sandbox(str(session.id))
    checks = await run_live_checks(sbx, n_var_a, n_var_b, resolved["type_a"], resolved["type_b"])
    selection = decide_test(resolved, checks)
    if selection.get("unsupported"):
        return await _assisted_run(message, session, context, [n_var_a, n_var_b], selection.get("reasoning", ""))

    recommended_test = selection["recommended_test"]
    reasoning = explain_test_choice(selection)

    # In GUIDED mode we pause here: show the assumption results + the chosen test,
    # log the assumption_check artifact (advances the rail), and let the user
    # continue to actually run it. In EXPLORE mode we just run it now.
    if mode == "guided":
        return _assumption_pause(n_var_a, n_var_b, recommended_test, reasoning, checks)

    return await _run_verified(session, context, n_var_a, n_var_b, recommended_test, reasoning, checks, requested_test, requested_confident)


# ── Verified (deterministic) run ──────────────────────────────────────────────

async def _run_verified_from_scratch(message, session, context, resolved, requested_test, requested_confident) -> dict[str, Any]:
    sbx = await get_or_create_sandbox(str(session.id))
    checks = await run_live_checks(sbx, resolved["var_a"], resolved["var_b"], resolved["type_a"], resolved["type_b"])
    selection = decide_test(resolved, checks)
    if selection.get("unsupported"):
        return await _assisted_run(message, session, context, [resolved["var_a"], resolved["var_b"]], selection.get("reasoning", ""))
    return await _run_verified(session, context, resolved["var_a"], resolved["var_b"], selection["recommended_test"], explain_test_choice(selection), checks, requested_test, requested_confident)


async def _run_verified(session, context, var_a, var_b, recommended_test, reasoning, checks, requested_test, requested_confident) -> dict[str, Any]:
    # Honor a confident, registry-supported explicit request as an override —
    # BUT never let it re-introduce an assumption the engine found violated:
    #  - non-parametric recommended vs parametric requested (normality/sample
    #    failed): e.g. "run a t-test" on non-normal data where the engine chose
    #    Mann-Whitney; or "run a pearson" where it chose Spearman.
    #  - a variance-robust variant (Welch) recommended vs its equal-variance
    #    counterpart requested (variance homogeneity failed): "run a t-test"
    #    where the engine chose Welch's t.
    # Accuracy wins over the literal request; the reasoning explains why.
    test_to_run = recommended_test
    if requested_confident and requested_test and get_test(requested_test) and requested_test != recommended_test:
        req_entry = get_test(requested_test)
        rec_entry = get_test(recommended_test)
        if _is_assumption_downgrade(recommended_test, requested_test):
            reasoning = (
                f"{reasoning} (You asked for {req_entry['display_name']}, but the assumption "
                f"checks show it isn't the right fit for this data, so I used "
                f"{rec_entry['display_name']} instead.)"
            )
        else:
            test_to_run = requested_test
            reasoning = f"{reasoning} You specifically asked for {req_entry['display_name']}, so I ran that instead."

    test_entry = get_test(test_to_run)
    code = render_template(test_entry["code_template"], col_a=var_a, col_b=var_b) if test_entry else None
    if not code:
        # Unknown template — fall back to the honest assisted tier rather than
        # silently producing nothing.
        return await _assisted_run("", session, context, [var_a, var_b], reasoning)

    sbx = await get_or_create_sandbox(str(session.id))
    exec_result = await execute_code(sbx, code)

    stdout = exec_result.get("stdout", "")
    if not exec_result.get("success") or not stdout.strip():
        # A verified template failed. We deliberately do NOT LLM-rewrite it (that
        # would break the determinism guarantee) — the template is known-correct,
        # so a failure means a data problem. Surface a clear diagnostic.
        detail = _first_error_line(exec_result.get("stderr", ""))
        return _text_result(
            f"I tried to run {test_entry['display_name']} on '{var_a}' and '{var_b}', but the data didn't allow it"
            + (f" ({detail})" if detail else "")
            + ". This usually means a column has unexpected values (e.g. text in a numeric column, or too few non-missing rows). "
            "Want me to check the column types first?"
        )

    narration = await _narrate(test_to_run, var_a, var_b, reasoning, stdout)

    p_value = _extract_p_value(stdout)
    statistic = _extract_statistic(stdout)

    # Post-hoc: for a SIGNIFICANT 3+-group omnibus test (ANOVA / Welch-ANOVA /
    # Kruskal), run pairwise comparisons to show WHICH groups differ.
    posthoc = None
    if test_entry.get("posthoc") and p_value is not None and p_value < 0.05:
        posthoc = await _run_posthoc(sbx, test_entry["posthoc"], var_a, var_b)

    # Publication-grade fields (df, N, effect-size value, per-group descriptives)
    # re-derived deterministically from the same verified stdout, so the report
    # layer can produce APA notation without re-running or guessing.
    pub_stats = extract_test_stats(test_to_run, stdout)

    artifact_content = {
        "test_name": test_to_run,
        "display_name": test_entry["display_name"],
        "p_value": p_value, "statistic": statistic, "variables": [var_a, var_b], "reasoning": reasoning,
        "assumption_results": checks, "interpretation": narration.plain_language_result,
        "raw_output": stdout, "suspect_result": narration.suspect_result, "suspect_reason": narration.suspect_reason,
        "posthoc": posthoc, "engine_verified": True, "alpha": 0.05,
        **pub_stats,
    }

    response_text = narration.plain_language_result
    # Authoritative group means/medians rendered deterministically from the verified
    # output — the LLM narration is instructed NOT to state per-group numbers because
    # it sometimes swapped which group had which value (a trust bug).
    group_summary = _format_group_descriptives(pub_stats.get("groups"))
    if group_summary:
        response_text += "\n\n" + group_summary
    if posthoc and posthoc.get("comparisons"):
        response_text += "\n\n" + _posthoc_summary(posthoc)
    if narration.suspect_result and narration.suspect_reason:
        response_text += f"\n\n⚠️ Note: {narration.suspect_reason}"

    suggested_next, next_action, nudge_style = _run_nudge(context.get("mode", "explore"), var_a, var_b, p_value, test_to_run)

    return {
        "text": response_text, "images": [], "artifact_content": artifact_content,
        "artifact_type": "test_result", "stage": "inferential", "variables_involved": [var_a, var_b],
        "code_used": code, "executions": [{"code": code, "output": stdout.rstrip() or "(no output)"}],
        "suggested_next": suggested_next, "next_action": next_action, "nudge_style": nudge_style,
        "engine_verified": True, "test_display_name": test_entry["display_name"],
        "is_hypothesis_candidate": False, "metered": True,
    }


# ── Post-hoc (which groups differ) ────────────────────────────────────────────

async def _run_posthoc(sbx, posthoc_key: str, outcome: str, grouping: str) -> Optional[dict[str, Any]]:
    code = render_posthoc(posthoc_key, outcome, grouping)
    if not code:
        return None
    exec_result = await execute_code(sbx, code)
    return _parse_posthoc(exec_result.get("stdout", ""), posthoc_key)


def _parse_posthoc(stdout: str, posthoc_key: str) -> Optional[dict[str, Any]]:
    comps = []
    for m in re.finditer(r"^(.+?) vs (.+?): p_adj=([0-9.eE\-]+), significant=(yes|no)", stdout, re.MULTILINE):
        comps.append({"group_a": m.group(1), "group_b": m.group(2), "p_adj": float(m.group(3)), "significant": m.group(4) == "yes"})
    if not comps:
        return None
    return {"method": posthoc_label(posthoc_key), "comparisons": comps}


def _format_group_descriptives(groups) -> str:
    """A correctly-labelled group mean/median summary, built from the verified
    stdout (not the LLM). Guarantees the group→value mapping is right even if the
    narration prose slips. Empty for non-grouped tests (correlation/regression)."""
    if not groups:
        return ""
    ctype = groups[0].get("center_type", "mean")
    stat_word = "means" if ctype == "mean" else "medians"
    parts = []
    for g in groups:
        try:
            parts.append(f"{g['label']}: {ctype} = {float(g['center']):.2f}, n = {int(g['n'])}")
        except (KeyError, TypeError, ValueError):
            continue
    return f"**Group {stat_word}:** " + "; ".join(parts) + "." if parts else ""


def _posthoc_summary(posthoc: dict[str, Any]) -> str:
    sig = [f"{c['group_a']} vs {c['group_b']} (p={c['p_adj']:.3f})" for c in posthoc["comparisons"] if c["significant"]]
    method = posthoc["method"]
    if sig:
        return f"**Post-hoc ({method}):** significant pairwise differences — " + "; ".join(sig) + "."
    return f"**Post-hoc ({method}):** the overall test was significant, but no pair survived correction."


# ── Guided assumption-check pause ─────────────────────────────────────────────

def _assumption_pause(var_a, var_b, recommended_test, reasoning, checks) -> dict[str, Any]:
    test_entry = get_test(recommended_test)
    display = test_entry["display_name"] if test_entry else recommended_test
    lines = [f"**Assumption checks — `{var_a}` vs `{var_b}`**", ""]
    for label, result in _readable_checks(checks):
        icon = {"pass": "✓", "fail": "✗"}.get(result, "–")
        lines.append(f"- {icon} {label}: {result}")
    lines.append("")
    lines.append(f"Based on these, the right test is **{display}**. {reasoning}")
    text = "\n".join(lines)

    artifact_content = {
        "recommended_test": recommended_test, "display_name": display,
        "reasoning": reasoning, "assumption_results": checks, "variables": [var_a, var_b],
    }
    return {
        "text": text, "images": [], "artifact_content": artifact_content,
        "artifact_type": "assumption_check", "stage": "assumption_checks", "variables_involved": [var_a, var_b],
        "code_used": None, "executions": [],
        "suggested_next": f"Ready to run the {display}?",
        "next_action": {"label": f"Run the {display}", "query": f"Run the statistical test on {var_a} and {var_b}"},
        "nudge_style": "directive",
        "is_hypothesis_candidate": False, "metered": False,
    }


# ── Assisted (LLM-chosen) tier — honest, clearly labelled ─────────────────────

async def _assisted_run(message, session, context, variables, why) -> dict[str, Any]:
    var_a, var_b = variables[0], variables[1]
    sbx = await get_or_create_sandbox(str(session.id))
    prompt = (
        f"There is no verified test in the library for '{var_a}' and '{var_b}' ({why}). "
        f"Write Python that reads /home/user/data.csv, runs the most appropriate statistical "
        f"analysis for these two columns, and prints the test name, test statistic, p-value, and "
        f"effect size. User request: {message or 'analyse these two variables'}"
    )
    response = await call_main_model(messages=[{"role": "user", "content": prompt}], system_prompt=ASSISTED_TEST_SYSTEM_PROMPT, tools=None, temperature=0.1)
    code = re.sub(r"```python\n?|```\n?", "", response.message.content or "").strip()

    exec_result = await execute_code(sbx, code)
    if not exec_result.get("success"):
        exec_result = await attempt_repair(sbx=sbx, original_code=code, stderr=exec_result.get("stderr", ""), llm_repair_fn=_make_repair_fn())
        if exec_result.get("repaired_code"):
            code = exec_result["repaired_code"]
    stdout = exec_result.get("stdout", "")
    if exec_result.get("repair_exhausted") or not stdout.strip():
        return _text_result("I couldn't complete that analysis — it's outside the verified test library and the code ran into an error I couldn't fix. Want to try a different pair of variables?")

    narration = await _narrate("an appropriate test", var_a, var_b, why, stdout)
    p_value = _extract_p_value(stdout)
    statistic = _extract_statistic(stdout)

    artifact_content = {
        "test_name": "assisted", "display_name": "LLM-assisted analysis",
        "p_value": p_value, "statistic": statistic, "variables": [var_a, var_b], "reasoning": why,
        "assumption_results": {}, "interpretation": narration.plain_language_result,
        "raw_output": stdout, "suspect_result": narration.suspect_result, "suspect_reason": narration.suspect_reason,
        "engine_verified": False, "alpha": 0.05,
    }
    response_text = (
        narration.plain_language_result
        + "\n\n> ⚠️ This analysis is **not from the verified test library** — the assistant chose and wrote it directly, "
        "so treat the result with more caution than a verified test."
    )
    if narration.suspect_result and narration.suspect_reason:
        response_text += f"\n\n⚠️ Note: {narration.suspect_reason}"

    return {
        "text": response_text, "images": exec_result.get("images", []), "artifact_content": artifact_content,
        "artifact_type": "test_result", "stage": "inferential", "variables_involved": [var_a, var_b],
        "code_used": code, "executions": [{"code": code, "output": stdout.rstrip() or "(no output)"}],
        "suggested_next": None, "next_action": None, "nudge_style": "soft",
        "engine_verified": False, "test_display_name": "LLM-assisted analysis",
        "is_hypothesis_candidate": False, "metered": True,
    }


# ── Verified regression (Goal 1) ──────────────────────────────────────────────

_REGRESSION_RE = re.compile(
    r"\b(regression|regress|\bpredict\b|\bmodel\b[^.?!]{0,40}\b(on|from|using|by)\b|"
    r"controlling for|adjusting for|multivariable|multivariate|covariat)\b",
    re.IGNORECASE,
)


def _is_regression_request(message: str) -> bool:
    return bool(_REGRESSION_RE.search(message))


async def _extract_regression_spec(message: str, columns: list[str]) -> RegressionSpec:
    col_list = ", ".join(columns)
    return await call_structured_output(
        messages=[{"role": "user", "content": f"Columns: {col_list}\n\nRequest: {message}"}],
        system_prompt=REGRESSION_EXTRACTION_SYSTEM_PROMPT, schema_class=RegressionSpec, temperature=0.0,
    )


def _match_column(name: str, columns: list[str]) -> Optional[str]:
    if not name:
        return None
    low = name.strip().lower()
    for c in columns:                       # exact (case-insensitive)
        if c.lower() == low:
            return c
    for c in columns:                       # substring
        if low in c.lower() or c.lower() in low:
            return c
    return None


async def _regression(message, session, context, profile, mode) -> dict[str, Any]:
    columns = list(profile.get("columns", {}).keys())
    spec = await _extract_regression_spec(message, columns)
    if not spec.is_regression or not spec.outcome:
        return _text_result(
            "Tell me which variable to predict (the outcome) and which predictors to use — "
            "e.g. \"predict exam_score from hours_studied and cohort\"."
        )

    outcome = _match_column(spec.outcome, columns)
    predictors = [m for m in (_match_column(p, columns) for p in spec.predictors) if m]
    predictors = list(dict.fromkeys(predictors))
    if not outcome:
        return _text_result(f"I couldn't match the outcome '{spec.outcome}' to a column. Available: {', '.join(columns[:12])}")
    if not predictors:
        return _text_result(f"I need at least one predictor column for the regression. Available: {', '.join(columns[:12])}")

    resolved = resolve_model(outcome, predictors, profile)
    if not resolved.get("ok"):
        return _text_result(resolved.get("reason", "I couldn't set up that regression."))

    code = render_regression(resolved["model_type"], resolved["outcome"], resolved["predictors"], resolved["categoricals"])
    sbx = await get_or_create_sandbox(str(session.id))
    exec_result = await execute_code(sbx, code)
    stdout = exec_result.get("stdout", "")
    # Judge success by the deterministic output marker, not the executor's success
    # flag: statsmodels warnings / the first-run pip install can write harmless
    # stderr, but if the model block printed, the regression genuinely ran.
    if "=== MODEL ===" not in stdout:
        stderr = exec_result.get("stderr", "") or ""
        if "statsmodels" in stderr or "No module named" in stderr:
            return _text_result(
                "I couldn't load the regression library (statsmodels) in the analysis sandbox. "
                "The model is set up correctly — retry in a moment, or the sandbox may lack network "
                "access to install it (the deployed image should include it)."
            )
        detail = _first_error_line(stderr)
        return _text_result(f"I couldn't fit that regression{(' (' + detail + ')') if detail else ''}. Check the columns have enough complete rows.")

    content = _parse_regression_output(stdout, resolved)
    narration = await call_structured_output(
        messages=[{"role": "user", "content": f"Model output:\n{stdout}\n\nInterpret it."}],
        system_prompt=REGRESSION_NARRATION_SYSTEM_PROMPT, schema_class=ConfirmatoryNarration, temperature=0.1,
    )
    display = content["display_name"]
    response_text = narration.plain_language_result
    if narration.suspect_result and narration.suspect_reason:
        response_text += f"\n\n⚠️ Note: {narration.suspect_reason}"

    if mode == "guided":
        nudge_style, suggested_next = "directive", "Next step: interpret these coefficients and add the model to your report."
        next_action = {"label": "Interpret & continue", "query": f"Interpret the regression of {resolved['outcome']}"}
    else:
        nudge_style, suggested_next, next_action = "soft", "Want to check the model's assumptions or try different predictors?", None

    return {
        "text": response_text, "images": [], "artifact_content": content,
        "artifact_type": "test_result", "stage": "inferential",
        "variables_involved": [resolved["outcome"]] + resolved["predictors"],
        "code_used": code, "executions": [{"code": code, "output": stdout.rstrip() or "(no output)"}],
        "suggested_next": suggested_next, "next_action": next_action, "nudge_style": nudge_style,
        "engine_verified": True, "test_display_name": display,
        "is_hypothesis_candidate": False, "metered": True,
    }


def _parse_regression_output(stdout: str, resolved: dict[str, Any]) -> dict[str, Any]:
    def f(label):
        m = re.search(rf"{re.escape(label)}[:\s]+([\-0-9.eE]+)", stdout)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    coefficients = []
    for m in re.finditer(r"^(.+?): coef=([\-0-9.eE]+), se=([\-0-9.eE]+), [tz]=([\-0-9.eE]+), p=([\-0-9.eE]+)(?:, or=([\-0-9.eE]+))?, ci=\[([\-0-9.eE]+), ([\-0-9.eE]+)\]", stdout, re.MULTILINE):
        coefficients.append({
            "name": m.group(1), "coef": float(m.group(2)), "se": float(m.group(3)),
            "statistic": float(m.group(4)), "p_value": float(m.group(5)),
            "odds_ratio": float(m.group(6)) if m.group(6) else None,
            "ci_low": float(m.group(7)), "ci_high": float(m.group(8)),
        })
    diagnostics = {
        "vif": {vm.group(1): float(vm.group(2)) for vm in re.finditer(r"VIF (.+?): ([\-0-9.eE]+)", stdout)},
        "breusch_pagan_p": f("Breusch-Pagan p (homoscedasticity)"),
        "durbin_watson": f("Durbin-Watson (independence)"),
        "residual_normality_p": f("Residual normality p"),
    }
    model_type = resolved["model_type"]
    display = "Logistic Regression" if model_type == "logistic" else "Linear Regression"
    p_value = f("LLR P-value") if model_type == "logistic" else f("P-value")
    return {
        "test_name": f"{model_type}_regression", "display_name": display,
        "model_type": model_type, "outcome": resolved["outcome"], "predictors": resolved["predictors"],
        "n": int(f("N")) if f("N") is not None else None,
        "r_squared": f("Pseudo R-squared") if model_type == "logistic" else f("R-squared"),
        "adj_r_squared": f("Adjusted R-squared"),
        # F(df1, df2) for the linear model's omnibus test — used by the APA write-up.
        "f_statistic": f("F-statistic") if model_type == "linear" else None,
        "p_value": p_value, "statistic": None,
        "coefficients": coefficients, "diagnostics": diagnostics,
        "reasoning": f"{display} of '{resolved['outcome']}' on {', '.join(resolved['predictors'])}.",
        "assumption_results": {}, "interpretation": "", "raw_output": stdout,
        "engine_verified": True, "alpha": 0.05,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _narrate(test_name, var_a, var_b, reasoning, stdout) -> ConfirmatoryNarration:
    return await call_structured_output(
        messages=[{"role": "user", "content": f"Test: {test_name}\nVariables: {var_a} vs {var_b}\nReasoning: {reasoning}\n\nRaw output:\n{stdout}\n\nWrite a plain-language interpretation."}],
        system_prompt=NARRATION_SYSTEM_PROMPT, schema_class=ConfirmatoryNarration, temperature=0.1,
    )


def _run_nudge(mode, var_a, var_b, p_value, test_name=None):
    """Directive next-step in guided mode, soft optional suggestion in explore."""
    if mode == "guided":
        return (
            "Next step: interpret this result and note the effect size, then add it to your report.",
            {"label": "Interpret & continue", "query": f"Interpret the result for {var_a} and {var_b} and what it means for my research question"},
            "directive",
        )
    # explore: soft, dismissible. Wording matches the analysis: a correlation is
    # a relationship (scatter), a group comparison is a difference.
    entry = get_test(test_name) if test_name else None
    is_correlation = bool(entry and entry.get("category") == "correlation")
    if p_value is not None and p_value < 0.05:
        if is_correlation:
            return ("The relationship is significant — want me to visualize it?", {"label": "Visualize it", "query": f"Plot {var_a} vs {var_b}"}, "soft")
        return ("The result is significant — want me to visualize the difference between groups?", {"label": "Visualize it", "query": f"Plot {var_a} by {var_b}"}, "soft")
    return ("Want to explore other variables or check a different relationship?", None, "soft")


def _readable_checks(checks: dict[str, str]):
    labels = {
        "normality_outcome": "Normality (outcome)", "normality_b": "Normality (second variable)",
        "variance_equal": "Equal variance across groups", "sample_size_ok": "Adequate sample size",
        "min_expected_cell": "Expected cell counts",
    }
    out = []
    for key, label in labels.items():
        val = checks.get(key)
        if val and val != NOT_APPLICABLE:
            out.append((label, val))
    return out


def _first_error_line(stderr: str) -> str:
    for line in reversed((stderr or "").strip().split("\n")):
        if line.strip():
            return line.strip()[:160]
    return ""


def _extract_variables(message, profile):
    columns = list(profile.get("columns", {}).keys())
    return match_columns(message, columns, profile)[:2]


def resolve_pair_variables(message, profile, focus_variables):
    """Decide which two columns a confirmatory request is about.

    Returns (variables, clarification) with exactly one truthy. The last-worked-on
    `focus_variables` are used ONLY as a fallback for a genuine follow-up that
    names NO column (e.g. "is that significant?"). If the user explicitly named a
    column, we NEVER silently borrow a *different* variable from context: doing so
    answered the wrong question with a confident, verified-looking result when a
    column name was mistyped (e.g. "test foobar and bp" ran age-vs-bp). In that
    case we ask, surfacing the column we did recognize."""
    named = _extract_variables(message, profile)
    variables = list(named)
    cols = list(profile.get("columns", {}).keys())
    if len(variables) == 0:
        variables = [v for v in (focus_variables or []) if v in cols][:2]
    if len(variables) >= 2:
        return variables[:2], None

    avail = ", ".join(cols[:10])
    if named:
        return None, (
            f"I recognized '{named[0]}', but I couldn't identify a second column to compare it with — "
            f"did you mistype a column name? Available columns: {avail}"
        )
    return None, (
        f"I need two columns to run a test. Which two would you like to compare? Available: {avail}"
    )


def _extract_p_value(stdout):
    match = re.search(r"[Pp]-value[:\s]+([0-9.eE\-]+)", stdout)
    if match:
        try: return float(match.group(1))
        except ValueError: return None
    return None


def _extract_statistic(stdout):
    patterns = [r"T-statistic[:\s]+([0-9.eE\-]+)", r"U-statistic[:\s]+([0-9.eE\-]+)", r"F-statistic[:\s]+([0-9.eE\-]+)", r"H-statistic[:\s]+([0-9.eE\-]+)", r"Chi-square statistic[:\s]+([0-9.eE\-]+)", r"Pearson r[:\s]+([0-9.eE\-]+)", r"Spearman rho[:\s]+([0-9.eE\-]+)"]
    for pat in patterns:
        match = re.search(pat, stdout)
        if match:
            try: return float(match.group(1))
            except ValueError: continue
    return None


def _text_result(text):
    return {
        "text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": None,
        "variables_involved": None, "code_used": None, "executions": [], "suggested_next": None,
        "next_action": None, "nudge_style": "soft", "is_hypothesis_candidate": False, "metered": False,
    }


def _make_repair_fn():
    async def repair_fn(original_code, error_summary, hint, temperature):
        prompt = repair_prompt(original_code, error_summary, hint)
        response = await call_main_model(messages=[{"role": "user", "content": prompt}], system_prompt="You are a Python debugging assistant. Return only corrected Python code, no markdown.", tools=None, temperature=temperature)
        return response.message.content or original_code
    return repair_fn
