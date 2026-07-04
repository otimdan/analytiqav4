import re
from typing import Any
from app.db.models import Session
from app.llm.fireworks_client import call_main_model
from app.config import FIREWORKS_MODEL_CHAT
from app.llm.prompts import ADVISORY_SYSTEM_PROMPT
from app.orchestrator.context_builder import format_context_for_prompt
from app.stats_engine.variable_classifier import classify_variable
from app.stats_engine.assumption_checks import check_normality
from app.profiling.cache import get_cached_profile


async def handle(message: str, session: Session, context: dict[str, Any]) -> dict[str, Any]:
    if _is_method_evaluation(message):
        return await _handle_method_evaluation(message, session, context)

    context_block = format_context_for_prompt(context)
    messages = [{"role": "user", "content": f"{context_block}\n\nQuestion: {message}"}]
    response = await call_main_model(messages=messages, system_prompt=ADVISORY_SYSTEM_PROMPT, tools=None, temperature=0.1, model=FIREWORKS_MODEL_CHAT)
    return _empty_result(text=response.message.content or "", stage="descriptive")


async def _handle_method_evaluation(message: str, session: Session, context: dict[str, Any]) -> dict[str, Any]:
    profile = get_cached_profile(str(session.id))
    if not profile:
        return _empty_result(text="I don't have your dataset profile yet. Try again in a moment.", stage="descriptive")

    columns = list(profile.get("columns", {}).keys())
    mentioned = [c for c in columns if c.lower() in message.lower()]

    assumption_notes = ""
    if mentioned:
        notes = []
        for col in mentioned[:2]:
            var_type = classify_variable(col, profile)
            normality = check_normality(col, profile)
            notes.append(f"'{col}': type={var_type}, normality={normality}")
        assumption_notes = "\n\nAssumption check results for mentioned variables:\n" + "\n".join(notes)

    context_block = format_context_for_prompt(context)
    messages = [{"role": "user", "content": f"{context_block}{assumption_notes}\n\nQuestion: {message}\n\nBased on the assumption check results above, advise whether the suggested method is appropriate. If not, suggest what would be better and why. End by asking if they want you to run the analysis."}]
    response = await call_main_model(messages=messages, system_prompt=ADVISORY_SYSTEM_PROMPT, tools=None, temperature=0.1, model=FIREWORKS_MODEL_CHAT)
    return _empty_result(text=response.message.content or "", stage="descriptive")


def _is_method_evaluation(message: str) -> bool:
    patterns = [
        r"\bwhat do you think of\b.{0,30}\b(anova|t.test|chi.square|regression|mann.whitney|kruskal|fisher|pearson|spearman)\b",
        r"\bis\b.{0,20}\b(anova|t.test|chi.square|regression|mann.whitney|kruskal)\b.{0,20}\b(appropriate|suitable|right|correct|okay|good)\b",
        r"\bshould i use\b.{0,30}\b(anova|t.test|chi.square|regression|mann.whitney)\b",
        r"\bcan i use\b.{0,30}\b(anova|t.test|chi.square|regression|mann.whitney)\b",
    ]
    for pat in patterns:
        if re.search(pat, message, re.IGNORECASE):
            return True
    return False


def _empty_result(text: str, stage: str) -> dict[str, Any]:
    return {"text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": stage, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False}
