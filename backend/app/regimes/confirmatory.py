import json
import re
from typing import Any
from app.db.models import Session, Message
from app.llm.fireworks_client import call_main_model, call_structured_output
from app.llm.prompts import confirmatory_system_prompt, NARRATION_SYSTEM_PROMPT, repair_prompt
from app.llm.schemas import ConfirmatoryNarration
from app.sandbox.manager import get_or_create_sandbox
from app.sandbox.executor import execute_code
from app.sandbox.repair import attempt_repair
from app.stats_engine.test_selector import select_test, is_multivariate_request, get_multivariate_fallback_message, explain_test_choice
from app.stats_engine.registry import get_test, get_code_template
from app.profiling.cache import get_cached_profile
from app.db.aio import run_db
from app.orchestrator.context_builder import format_context_for_prompt


async def handle(message: str, session: Session, context: dict[str, Any], recent_messages: list[Message]) -> dict[str, Any]:
    profile = await run_db(get_cached_profile, str(session.id))
    if not profile:
        return _text_result("I need your dataset profile first. Try again in a moment.", "inferential")

    if is_multivariate_request(message):
        variables = _extract_variables(message, profile)
        return _text_result(get_multivariate_fallback_message(variables), "inferential")

    variables = _extract_variables(message, profile)
    if len(variables) < 2:
        return _text_result(f"I need two variables to run a test. Which two columns would you like to compare? Available: {', '.join(list(profile['columns'].keys())[:10])}", "inferential")

    var_a, var_b = variables[0], variables[1]
    selection = select_test(var_a, var_b, profile)

    if selection["needs_clarification"]:
        return _text_result(selection["clarification_reason"] or "I need more information to pick the right test.", "inferential")

    recommended_test = selection["recommended_test"]
    reasoning = explain_test_choice(selection)
    override_test = _detect_requested_test(message)
    run_both = override_test is not None and override_test != recommended_test

    test_entry = get_test(recommended_test)
    template = get_code_template(test_entry["code_template"]) if test_entry else None
    system_prompt = confirmatory_system_prompt(test_name=test_entry["display_name"] if test_entry else recommended_test, test_reasoning=reasoning, variables=[var_a, var_b])

    code_prompt = f"Write Python code to run {recommended_test} on '{var_a}' and '{var_b}'. Template pattern:\n{template}\n\nFill in: outcome='{var_a}', grouping='{var_b}'. Print all key statistics."
    if run_both:
        override_entry = get_test(override_test)
        override_template = get_code_template(override_entry["code_template"]) if override_entry else None
        code_prompt += f"\n\nAlso run {override_test} as specifically requested. Label each result clearly."

    code_response = await call_main_model(messages=[{"role": "user", "content": code_prompt}], system_prompt=system_prompt, tools=None, temperature=0.05)
    generated_code = re.sub(r"```python\n?|```\n?", "", code_response.message.content or "").strip()

    sbx = await get_or_create_sandbox(str(session.id))
    exec_result = await execute_code(sbx, generated_code)

    if not exec_result["success"]:
        exec_result = await attempt_repair(sbx=sbx, original_code=generated_code, stderr=exec_result["stderr"], llm_repair_fn=_make_repair_fn())
        if exec_result.get("repaired_code"):
            generated_code = exec_result["repaired_code"]

    stdout = exec_result.get("stdout", "")
    if exec_result.get("repair_exhausted") or not stdout:
        return _text_result("The statistical test ran into an error I couldn't fix. Want me to check the column types first?", "inferential")

    narration: ConfirmatoryNarration = await call_structured_output(
        messages=[{"role": "user", "content": f"Test: {recommended_test}\nVariables: {var_a} vs {var_b}\nReasoning: {reasoning}\n\nRaw output:\n{stdout}\n\nWrite a plain-language interpretation."}],
        system_prompt=NARRATION_SYSTEM_PROMPT, schema_class=ConfirmatoryNarration, temperature=0.1,
    )

    p_value = _extract_p_value(stdout)
    statistic = _extract_statistic(stdout)

    artifact_content = {
        "test_name": recommended_test, "display_name": test_entry["display_name"] if test_entry else recommended_test,
        "p_value": p_value, "statistic": statistic, "variables": [var_a, var_b], "reasoning": reasoning,
        "assumption_results": selection.get("assumption_results", {}), "interpretation": narration.plain_language_result,
        "raw_output": stdout, "suspect_result": narration.suspect_result, "suspect_reason": narration.suspect_reason, "override_test_run": run_both,
    }

    response_text = narration.plain_language_result
    if narration.suspect_result and narration.suspect_reason:
        response_text += f"\n\n⚠️ Note: {narration.suspect_reason}"

    suggested_next = None
    if context.get("suggestion_mode"):
        if p_value is not None and p_value < 0.05:
            suggested_next = "The result is significant — want me to visualize the difference between groups?"
        else:
            suggested_next = "Want to explore other variables or check a different relationship?"

    executions = [{"code": generated_code, "output": stdout.rstrip() or "(no output)"}]
    return {"text": response_text, "images": exec_result.get("images", []), "artifact_content": artifact_content, "artifact_type": "test_result", "stage": "inferential", "variables_involved": [var_a, var_b], "code_used": generated_code, "executions": executions, "suggested_next": suggested_next, "is_hypothesis_candidate": False}


def _extract_variables(message, profile):
    columns = list(profile.get("columns", {}).keys())
    return [col for col in columns if col.lower() in message.lower()][:2]


def _detect_requested_test(message):
    test_aliases = {"t-test": "independent_t", "t test": "independent_t", "anova": "one_way_anova", "chi-square": "chi_square", "chi square": "chi_square", "mann-whitney": "mann_whitney", "mann whitney": "mann_whitney", "kruskal": "kruskal_wallis", "kruskal-wallis": "kruskal_wallis", "pearson": "pearson", "spearman": "spearman", "fisher": "fisher_exact"}
    msg_lower = message.lower()
    for alias, test_name in test_aliases.items():
        if alias in msg_lower:
            return test_name
    return None


def _extract_p_value(stdout):
    match = re.search(r"[Pp]-value[:\s]+([0-9.eE\-]+)", stdout)
    if match:
        try: return float(match.group(1))
        except ValueError: return None
    return None


def _extract_statistic(stdout):
    patterns = ["T-statistic[:\s]+([0-9.eE\-]+)", "U-statistic[:\s]+([0-9.eE\-]+)", "F-statistic[:\s]+([0-9.eE\-]+)", "H-statistic[:\s]+([0-9.eE\-]+)", "Chi-square statistic[:\s]+([0-9.eE\-]+)", "Pearson r[:\s]+([0-9.eE\-]+)", "Spearman rho[:\s]+([0-9.eE\-]+)"]
    for pat in patterns:
        match = re.search(pat, stdout)
        if match:
            try: return float(match.group(1))
            except ValueError: continue
    return None


def _text_result(text, stage):
    return {"text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": stage, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False}


def _make_repair_fn():
    async def repair_fn(original_code, error_summary, hint, temperature):
        prompt = repair_prompt(original_code, error_summary, hint)
        response = await call_main_model(messages=[{"role": "user", "content": prompt}], system_prompt="You are a Python debugging assistant. Return only corrected Python code, no markdown.", tools=None, temperature=temperature)
        return response.message.content or original_code
    return repair_fn
