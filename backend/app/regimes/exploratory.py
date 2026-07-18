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
            mentioned = _extract_mentioned_columns(message, col_names)
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

    if not final_text:
        final_text = "I reached the maximum number of steps without a clean result. Here's what I found so far."

    code_used = "\n\n".join(all_code_blocks) if all_code_blocks else None
    stage = "visualisation" if all_images else "descriptive"
    variables = _extract_mentioned_columns(message, col_names)

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


def _extract_mentioned_columns(message, columns):
    # Match real column names against the message (same approach as the
    # confirmatory handler), case-insensitively.
    return [col for col in columns if col.lower() in message.lower()]


_INFERENTIAL_RE = re.compile(
    r"\b(regression|regress|predict|predictor|coefficient|r.?squared|\bols\b|\bglm\b|"
    r"logistic|multivariate|controlling for|adjust(ing)? for|covariat|model (the|exam|score|outcome))\b",
    re.IGNORECASE,
)


def _is_inferential_request(message: str) -> bool:
    return bool(_INFERENTIAL_RE.search(message))
