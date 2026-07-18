import re
from typing import Any, Optional
from app.db.models import Session, Message
from app.llm.fireworks_client import call_main_model, call_structured_output
from app.llm.prompts import NARRATION_SYSTEM_PROMPT, repair_prompt, ASSISTED_TEST_SYSTEM_PROMPT
from app.llm.schemas import ConfirmatoryNarration
from app.sandbox.manager import get_or_create_sandbox
from app.sandbox.executor import execute_code
from app.sandbox.repair import attempt_repair
from app.stats_engine.test_selector import (
    resolve_pair, decide_test, resolve_requested_test,
    is_multivariate_request, get_multivariate_fallback_message, explain_test_choice,
)
from app.stats_engine.registry import get_test, render_template
from app.stats_engine.assumption_checks import run_live_checks, PASS, FAIL, NOT_APPLICABLE
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

    if is_multivariate_request(message):
        variables = _extract_variables(message, profile)
        return _text_result(get_multivariate_fallback_message(variables))

    variables = _extract_variables(message, profile)
    if len(variables) < 2:
        # The message didn't name two columns (e.g. "is that significant?").
        # Reuse the variables the user was last working with (last chart/test)
        # so a follow-up runs on those instead of re-asking which columns.
        focus = [v for v in (context.get("focus_variables") or []) if v in profile.get("columns", {})]
        variables = (variables + [v for v in focus if v not in variables])[:2]
    if len(variables) < 2:
        return _text_result(f"I need two variables to run a test. Which two columns would you like to compare? Available: {', '.join(list(profile['columns'].keys())[:10])}")

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

    artifact_content = {
        "test_name": test_to_run,
        "display_name": test_entry["display_name"],
        "p_value": p_value, "statistic": statistic, "variables": [var_a, var_b], "reasoning": reasoning,
        "assumption_results": checks, "interpretation": narration.plain_language_result,
        "raw_output": stdout, "suspect_result": narration.suspect_result, "suspect_reason": narration.suspect_reason,
        "engine_verified": True, "alpha": 0.05,
    }

    response_text = narration.plain_language_result
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
    return [col for col in columns if col.lower() in message.lower()][:2]


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
