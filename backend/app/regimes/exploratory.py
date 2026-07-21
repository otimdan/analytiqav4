import json
import re
from typing import Any
from app.db.models import Session, Message
from app.config import MAX_STEPS
from app.llm.fireworks_client import call_main_model
from app.llm.prompts import EXPLORATORY_SYSTEM_PROMPT
from app.sandbox.manager import get_or_create_sandbox
from app.sandbox.executor import execute_code, build_tool_result_string
from app.sandbox.repair import attempt_repair
from app.orchestrator.context_builder import format_context_for_prompt
from app.profiling.cache import get_cached_profile
from app.stats_engine.chart_selector import recommend_chart
from app.stats_engine.column_matcher import match_columns
from app.db.aio import run_db

_EXECUTE_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": "Execute Python code in a secure sandboxed environment. Use pandas to analyze data.csv pre-loaded at /home/user/data.csv. Use matplotlib to create plots — save to /home/user/output.png. Always print() results.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Valid Python code to execute."}}, "required": ["code"]},
    },
}


async def handle(message: str, session: Session, context: dict[str, Any], recent_messages: list[Message]) -> dict[str, Any]:
    sbx = await get_or_create_sandbox(str(session.id))
    context_block = format_context_for_prompt(context)

    # Real column names, matched against the message directly. (The profile
    # summary text has no backticks, so parsing backticks out of it found
    # nothing — which left chart artifacts with no variables_involved and broke
    # the "plot X vs Y" -> "is that significant?" context carry.)
    profile = await run_db(get_cached_profile, str(session.id))
    col_names = list((profile or {}).get("columns", {}).keys())

    # Deliberate "plot X vs Y" flow: when the user explicitly asks for a chart,
    # pick an appropriate chart type from the mentioned columns' types and steer
    # the model toward it, so visualizations are reliable and well-formed rather
    # than incidental.
    chart_rec = None
    plot_directive = ""
    if _is_plot_request(message):
        if profile:
            mentioned = _extract_mentioned_columns(message, col_names, profile)
            chart_rec = recommend_chart(mentioned, profile)
        if chart_rec:
            plot_directive = f"\n\nThe user wants a visualization. {chart_rec.directive} You MUST produce this chart."
        else:
            plot_directive = "\n\nThe user wants a visualization — produce a clear, well-labeled chart appropriate to the variables."

    messages = []
    for turn in context["recent_turns"]:
        messages.append(turn)
    user_content = f"{context_block}\n\n{message}{plot_directive}" if not messages else f"{message}{plot_directive}"
    messages.append({"role": "user", "content": user_content})

    steps = 0
    all_images: list[str] = []
    all_code_blocks: list[str] = []
    executions: list[dict[str, Any]] = []
    final_text = ""

    while steps < MAX_STEPS:
        # The model has no visibility into the step budget, so an open-ended ask
        # ("analyse my data") explores straight into the wall. Warn it in time to
        # land the answer itself, which is cheaper and better than synthesising
        # for it after the fact.
        if steps == MAX_STEPS - 2:
            messages.append({"role": "user", "content": _WRAP_UP_NUDGE})

        response = await call_main_model(messages=messages, system_prompt=EXPLORATORY_SYSTEM_PROMPT, tools=[_EXECUTE_CODE_TOOL], tool_choice="auto", temperature=0.1)
        msg = response.message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            final_text = msg.content or ""
            break

        for tc in msg.tool_calls:
            if tc.function.name != "execute_code":
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Unknown tool: {tc.function.name}"})
                continue

            args = json.loads(tc.function.arguments)
            code = args.get("code", "")
            all_code_blocks.append(code)
            exec_result = await execute_code(sbx, code)

            if not exec_result["success"]:
                exec_result = await attempt_repair(sbx=sbx, original_code=code, stderr=exec_result["stderr"], llm_repair_fn=_make_repair_fn(session))
                if exec_result.get("repaired_code"):
                    all_code_blocks[-1] = exec_result["repaired_code"]

            all_images.extend(exec_result.get("images", []))
            tool_str = build_tool_result_string(exec_result)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_str})
            executions.append({"code": all_code_blocks[-1], "output": _format_execution_output(exec_result)})

            if exec_result.get("repair_exhausted"):
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": "Code execution failed after multiple attempts. Explain the issue to the user and suggest a simpler alternative."})

        steps += 1

    # An explicit chart request that produced no chart is a failed answer, not a
    # partial one — long wrangling sessions routinely end with the model having
    # forgotten the plot. Spend one targeted turn on it rather than returning
    # code and no figure.
    if _is_plot_request(message) and not all_images:
        await _retry_chart(messages, sbx, all_images, all_code_blocks, executions)

    # Any empty answer gets a synthesis attempt, not just an exhausted budget:
    # the model can also stop calling tools while returning no content (a long,
    # output-heavy session makes this likely), and that path used to fall
    # straight to the apology below.
    if not final_text:
        final_text = await _synthesize(messages)

    if not final_text:
        final_text = "I ran the analysis but couldn't put together a written summary. The code and output below show what I found."

    code_used = "\n\n".join(all_code_blocks) if all_code_blocks else None
    stage = "visualisation" if all_images else "descriptive"
    variables = _extract_mentioned_columns(message, col_names, profile)

    chart_type = chart_rec.chart_type if chart_rec else _infer_chart_type(all_code_blocks)
    chart_caption = chart_rec.rationale if chart_rec else None
    if chart_rec and chart_rec.columns:
        variables = chart_rec.columns

    artifact_content = None
    artifact_type = None
    if all_images:
        artifact_type = "chart"
        artifact_content = {"chart_type": chart_type, "variables": variables, "image_count": len(all_images)}
    elif final_text and len(final_text) > 100:
        artifact_type = "summary"
        artifact_content = {"text_preview": final_text[:500], "variables": variables}

    suggested_next = None
    next_action = None
    nudge_style = "soft"
    # Nudges are always eligible now; mode decides the tone. After a chart with
    # two variables, point toward a formal test — directively in guided mode,
    # softly in explore.
    if all_images and len(variables) >= 2:
        next_action = {"label": "Run the test", "query": f"Run a statistical test on {variables[0]} and {variables[1]}"}
        if context.get("mode") == "guided":
            nudge_style = "directive"
            suggested_next = "Next step: run a statistical test to confirm this pattern."
        else:
            suggested_next = "Want to test whether that pattern is statistically significant?"

    # If the free-form path did an inferential analysis (regression/modelling),
    # it's outside the verified test library — badge it honestly so a regression
    # result doesn't read like a verified test. append the caveat to the text.
    verification = None
    if _is_inferential_request(message):
        verification = "Exploratory model (not verified)"
        final_text += (
            "\n\n> ⚠️ This is an **exploratory analysis**, not from the verified test library — "
            "the assistant wrote it directly, so treat the result with more caution."
        )

    return {"text": final_text, "images": all_images, "artifact_content": artifact_content, "artifact_type": artifact_type, "stage": stage, "variables_involved": variables, "code_used": code_used, "executions": executions, "chart_caption": chart_caption, "suggested_next": suggested_next, "next_action": next_action, "nudge_style": nudge_style, "engine_verified": False if verification else None, "test_display_name": verification, "is_hypothesis_candidate": False}


_WRAP_UP_NUDGE = (
    "You have two tool calls left. Stop exploring and write your final answer now "
    "from the results you already have."
)

_SYNTHESIS_PROMPT = (
    "No further code can run. Write the final answer now from the results above: "
    "lead with the direct insight, cite the key numbers you found, and state plainly "
    "what you could not determine. Do not apologise and do not mention steps, "
    "budgets, or limits."
)

_CHART_RETRY_PROMPT = (
    "You still owe the user the chart they asked for and none was produced. Make one "
    "execute_code call that draws it from the results you already have. Save with "
    "exactly: plt.savefig('/home/user/output.png'); plt.close(). Nothing else."
)


async def _retry_chart(messages, sbx, all_images, all_code_blocks, executions) -> None:
    """Spend one turn recovering a chart the model was asked for but never drew.

    Mutates the accumulator lists in place. Best-effort: any failure leaves the
    response as it was rather than losing the analysis that did succeed.
    """
    try:
        messages.append({"role": "user", "content": _CHART_RETRY_PROMPT})
        response = await call_main_model(
            messages=messages,
            system_prompt=EXPLORATORY_SYSTEM_PROMPT,
            tools=[_EXECUTE_CODE_TOOL],
            tool_choice="auto",
            temperature=0.1,
        )
        msg = response.message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return

        for tc in msg.tool_calls:
            if tc.function.name != "execute_code":
                continue
            code = json.loads(tc.function.arguments).get("code", "")
            all_code_blocks.append(code)
            exec_result = await execute_code(sbx, code)
            all_images.extend(exec_result.get("images", []))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": build_tool_result_string(exec_result)})
            executions.append({"code": code, "output": _format_execution_output(exec_result)})
    except Exception:
        return


async def _synthesize(messages: list[dict[str, Any]]) -> str:
    """Force a written answer out of the model once the step budget is spent.

    Tools are withheld so the model cannot start another round of exploration.
    A failure here is not worth losing the whole response over — the caller
    falls back to a plain message when this returns empty.
    """
    try:
        response = await call_main_model(
            messages=[*messages, {"role": "user", "content": _SYNTHESIS_PROMPT}],
            system_prompt=EXPLORATORY_SYSTEM_PROMPT,
            tools=None,
            temperature=0.1,
        )
        return response.message.content or ""
    except Exception:
        return ""


def _format_execution_output(exec_result: dict) -> str:
    parts = []
    if exec_result.get("stdout"):
        parts.append(exec_result["stdout"].rstrip())
    if exec_result.get("stderr"):
        parts.append("[error]\n" + exec_result["stderr"].rstrip())
    if not parts and exec_result.get("images"):
        parts.append(f"[{len(exec_result['images'])} chart(s) generated]")
    return "\n".join(parts).strip() or "(no output)"


def _make_repair_fn(session: Session):
    async def repair_fn(original_code, error_summary, hint, temperature):
        from app.llm.prompts import repair_prompt
        prompt = repair_prompt(original_code, error_summary, hint)
        response = await call_main_model(messages=[{"role": "user", "content": prompt}], system_prompt="You are a Python debugging assistant. Return only corrected Python code.", tools=None, temperature=temperature)
        return response.message.content or original_code
    return repair_fn


_PLOT_REQUEST_RE = re.compile(
    r"\b(plot|chart|graph|visuali[sz]e|visuali[sz]ation|scatter|histogram|hist\b|"
    r"bar ?chart|box ?plot|boxplot|heatmap|line ?chart|pie ?chart|"
    r"show me (a|the)?\s*(chart|graph|plot|distribution|trend)|"
    r"draw (a|me)?|display (a|the)?\s*(chart|graph|plot))\b",
    re.IGNORECASE,
)


def _is_plot_request(message: str) -> bool:
    return bool(_PLOT_REQUEST_RE.search(message))


def _infer_chart_type(code_blocks):
    combined = " ".join(code_blocks).lower()
    if "scatter" in combined: return "scatter"
    if "bar" in combined or "barh" in combined: return "bar"
    if "hist" in combined: return "histogram"
    if "box" in combined: return "box"
    if "line" in combined: return "line"
    if "heatmap" in combined: return "heatmap"
    return "chart"


def _extract_mentioned_columns(message, columns, profile=None):
    # Token-sequence matching, so "exam score" finds exam_score. A plain
    # substring test missed every natural phrasing, which left charts with no
    # variables_involved and broke the "plot X vs Y" -> "is that significant?"
    # context carry.
    return match_columns(message, columns, profile)


_INFERENTIAL_RE = re.compile(
    r"\b(regression|regress|predict|predictor|coefficient|r.?squared|\bols\b|\bglm\b|"
    r"logistic|multivariate|controlling for|adjust(ing)? for|covariat|model (the|exam|score|outcome)|"
    # Meta-analysis. The engine has no verified templates for pooling, so these
    # get hand-written by the model — DerSimonian-Laird, Freeman-Tukey
    # back-transforms and all — and must be badged as unverified. A pooled
    # estimate reads far more authoritative than it is.
    r"meta.?analy\w*|forest plot|funnel plot|pooled|random.?effects?|fixed.?effects?|"
    r"heterogeneity|i.?squared|tau.?squared|dersimonian|mantel.?haenszel|"
    r"freeman.?tukey|egger|publication bias|(odds|risk|hazard) ratio)\b",
    re.IGNORECASE,
)


def _is_inferential_request(message: str) -> bool:
    return bool(_INFERENTIAL_RE.search(message))
