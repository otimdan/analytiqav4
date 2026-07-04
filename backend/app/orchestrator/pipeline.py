import asyncio
import re
from typing import Any, AsyncGenerator

from app.config import FEEDBACK_EVERY_N_TURNS
from app.db.models import Session, Message
from app.db.sessions import increment_feedback_count, update_flags, get_session
from app.db.artifacts import log_artifact, find_similar_artifact, mark_superseded
from app.db.hypothesis_candidates import get_pending_candidate
from app.profiling.cache import get_cached_profile, profile_is_ready

from app.orchestrator.classifier import classify_intent, is_off_topic
from app.orchestrator.hypothesis_watcher import check_message_for_hypothesis, check_orientation_trigger
from app.orchestrator.context_builder import build_context
from app.orchestrator.validator import validate_output, get_fallback_message

from app.regimes import advisory, pedagogy, exploratory, confirmatory, orientation, meta


async def process_message(
    message: str,
    session: Session,
    recent_messages: list[Message],
    source_message_id: str,
    is_first_reply: bool = False,
) -> AsyncGenerator[dict[str, Any], None]:

    if is_off_topic(message):
        yield {"type": "text", "content": "I'm focused on data analysis — ask me something about your dataset.", "regime": "meta", "show_feedback": False}
        return

    if not profile_is_ready(str(session.id)):
        yield {"type": "text", "content": "Still analyzing your dataset — try again in a moment.", "regime": "meta", "show_feedback": False}
        return

    has_pending = get_pending_candidate(str(session.id)) is not None

    classification_task = asyncio.create_task(classify_intent(message=message, recent_messages=recent_messages, has_pending_candidate=has_pending))
    hypothesis_task = asyncio.create_task(check_message_for_hypothesis(message=message, session=session, source_message_id=source_message_id, is_first_reply=is_first_reply))

    if not session.suggestion_mode and check_orientation_trigger(message):
        update_flags(str(session.id), suggestion_mode=True)

    classification, hypothesis_result = await asyncio.gather(classification_task, hypothesis_task)
    confirm_prompt = hypothesis_result.get("confirm_prompt")

    updated_session = get_session(str(session.id)) or session
    context = build_context(session=updated_session, recent_messages=recent_messages)

    regime = classification.regime
    needs_disambiguation = classification.needs_disambiguation

    if needs_disambiguation:
        yield {"type": "disambiguation", "content": None, "prompt": {"question": "Would you like a quick look or a formal test?", "options": ["Quick look", "Run a test"]}, "regime": "meta", "show_feedback": False}
        if confirm_prompt:
            yield {"type": "confirmation_prompt", "content": confirm_prompt, "regime": "meta", "show_feedback": False}
        return

    if regime in ["exploratory", "confirmatory"] and not updated_session.dataset_csv:
        yield {
            "type": "text",
            "content": (
                "Your dataset is no longer loaded in this session — the uploaded file "
                "isn't available anymore, so I can't run the analysis. Please re-upload "
                "your CSV to continue."
            ),
            "regime": "meta",
            "show_feedback": False,
        }
        return

    if regime in ["exploratory", "confirmatory"]:
        shortcut = await _check_execution_needed(message=message, session_id=str(session.id), context=context)
        if shortcut:
            yield shortcut
            if confirm_prompt:
                yield {"type": "confirmation_prompt", "content": confirm_prompt, "regime": "meta", "show_feedback": False}
            new_count = increment_feedback_count(str(session.id))
            yield {"type": "meta", "show_feedback": new_count % FEEDBACK_EVERY_N_TURNS == 0}
            return

    raw_result = await _dispatch(regime=regime, message=message, session=updated_session, context=context, recent_messages=recent_messages)

    validation = validate_output(regime=regime, response_text=raw_result.get("text", ""), artifact_content=raw_result.get("artifact_content"), has_images=bool(raw_result.get("images")))

    if not validation.passed:
        print(f"[pipeline] Validation failed for regime={regime}: {validation.failure_reason}")
        yield {"type": "text", "content": get_fallback_message(regime, validation.failure_reason or ""), "regime": regime, "show_feedback": False}
        return

    artifact_id = None
    if raw_result.get("artifact_content"):
        artifact = await _log_artifact(raw_result=raw_result, session_id=str(session.id), message_id=source_message_id, regime=regime)
        artifact_id = str(artifact.id) if artifact else None

    new_count = increment_feedback_count(str(session.id))
    show_feedback = new_count % FEEDBACK_EVERY_N_TURNS == 0

    for execution in raw_result.get("executions", []):
        yield {"type": "code_execution", "code": execution.get("code", ""), "output": execution.get("output", ""), "regime": regime, "show_feedback": False}

    if validation.cleaned_text:
        yield {"type": "text", "content": validation.cleaned_text, "regime": regime, "artifact_id": artifact_id, "show_feedback": show_feedback}

    for image_b64 in raw_result.get("images", []):
        yield {"type": "image", "content": image_b64, "regime": regime, "show_feedback": False}

    if confirm_prompt:
        yield {"type": "confirmation_prompt", "content": confirm_prompt, "regime": "meta", "show_feedback": False}

    if updated_session.suggestion_mode and raw_result.get("suggested_next"):
        yield {"type": "guidance_suggestion", "content": raw_result["suggested_next"], "is_hypothesis_candidate": raw_result.get("is_hypothesis_candidate", False), "regime": regime, "show_feedback": False}


async def _dispatch(regime, message, session, context, recent_messages) -> dict[str, Any]:
    if regime == "advisory":
        return await advisory.handle(message, session, context)
    if regime == "pedagogy":
        return await pedagogy.handle(message, context)
    if regime == "exploratory":
        return await exploratory.handle(message, session, context, recent_messages)
    if regime == "confirmatory":
        return await confirmatory.handle(message, session, context, recent_messages)
    if regime == "orientation":
        return await orientation.handle(session, context)
    if regime == "meta":
        return await meta.handle(message, session, context)
    return {"text": "I wasn't sure how to handle that. Could you rephrase?", "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False}


async def _check_execution_needed(message, session_id, context) -> dict[str, Any] | None:
    profile_questions = [
        r"\b(how many (rows|columns|observations))\b", r"\bcolumn names\b",
        r"\bwhat (columns|variables) (are|do I have)\b", r"\bsample size\b",
        r"\bdataset (size|shape|dimensions)\b",
    ]
    for pat in profile_questions:
        if re.search(pat, message, re.IGNORECASE):
            return {"type": "text", "content": context.get("profile_summary", ""), "regime": "advisory", "show_feedback": False, "shortcut": "profile"}

    profile = get_cached_profile(session_id)
    if not profile:
        return None

    mentioned_columns = [col for col in profile.get("columns", {}).keys() if col.lower() in message.lower()]
    if len(mentioned_columns) >= 2:
        existing = find_similar_artifact(session_id=session_id, stage="exploratory", artifact_type="chart", variables_involved=mentioned_columns)
        if existing:
            return {"type": "cached_artifact", "content": f"Here's the previous result for {' and '.join(mentioned_columns)} — want me to run it fresh?", "artifact_id": str(existing.id), "regime": "exploratory", "show_feedback": False, "shortcut": "cached_artifact"}
    return None


async def _log_artifact(raw_result, session_id, message_id, regime) -> Any:
    stage = raw_result.get("stage")
    artifact_type = raw_result.get("artifact_type")
    variables = raw_result.get("variables_involved") or []
    if not stage or not artifact_type:
        return None

    if variables:
        existing = find_similar_artifact(session_id=session_id, stage=stage, artifact_type=artifact_type, variables_involved=variables)
        new_artifact = log_artifact(session_id=session_id, stage=stage, artifact_type=artifact_type, content=raw_result.get("artifact_content", {}), message_id=message_id, code_used=raw_result.get("code_used"), variables_involved=variables)
        if existing:
            mark_superseded(str(existing.id), str(new_artifact.id))
        return new_artifact

    return log_artifact(session_id=session_id, stage=stage, artifact_type=artifact_type, content=raw_result.get("artifact_content", {}), message_id=message_id, code_used=raw_result.get("code_used"), variables_involved=variables)
