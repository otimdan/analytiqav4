import asyncio
import re
from typing import Any, AsyncGenerator

from app.config import FEEDBACK_EVERY_N_TURNS
from app.db.models import Session, Message
from app.db.sessions import increment_feedback_count, get_session
from app.db.artifacts import log_artifact, find_similar_artifact, mark_superseded
from app.db.hypothesis_candidates import get_pending_candidate
from app.db.usage import get_usage_summary, record_usage
from app.db.aio import run_db
from app.profiling.cache import get_cached_profile, profile_is_ready

from app.orchestrator.classifier import classify_intent, is_off_topic
from app.orchestrator.hypothesis_watcher import check_message_for_hypothesis
from app.orchestrator.context_builder import build_context
from app.orchestrator.validator import validate_output, get_fallback_message

from app.regimes import advisory, pedagogy, exploratory, confirmatory, orientation, meta, cleaning
from app.logging_config import logger
from app.observability import capture_event


def _analytics_id(session, updated_session) -> str:
    """Distinct id for analytics: the user when known, else the session (so
    anonymous funnels still count). Never carries dataset content."""
    uid = getattr(updated_session, "user_id", None) or getattr(session, "user_id", None)
    return str(uid) if uid else str(session.id)


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

    if not await run_db(profile_is_ready, str(session.id)):
        yield {"type": "text", "content": "Still analyzing your dataset — try again in a moment.", "regime": "meta", "show_feedback": False}
        return

    mode = getattr(session, "mode", "explore")
    has_pending = await run_db(get_pending_candidate, str(session.id)) is not None

    classification_task = asyncio.create_task(classify_intent(message=message, recent_messages=recent_messages, has_pending_candidate=has_pending, mode=mode))
    # In guided mode the project is tracked from the start; in explore mode we
    # never track. The watcher only silently records the research question text
    # (for guided) and never emits a competing "track as project?" prompt.
    hypothesis_task = asyncio.create_task(check_message_for_hypothesis(message=message, session=session, source_message_id=source_message_id, is_first_reply=is_first_reply, mode=mode))

    classification, _hypothesis_result = await asyncio.gather(classification_task, hypothesis_task)

    updated_session = await run_db(get_session, str(session.id)) or session
    context = await run_db(build_context, session=updated_session, recent_messages=recent_messages)

    regime = classification.regime
    needs_disambiguation = classification.needs_disambiguation

    if needs_disambiguation:
        yield {"type": "disambiguation", "content": None, "prompt": {"question": "Would you like a quick look or a formal test?", "options": ["Quick look", "Run a test"]}, "regime": "meta", "show_feedback": False}
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
            new_count = await run_db(increment_feedback_count, str(session.id))
            yield {"type": "meta", "show_feedback": new_count % FEEDBACK_EVERY_N_TURNS == 0}
            return

    # Meter the compute-heavy regimes against the user's monthly plan cap. Gate
    # before spending compute; record after it's actually spent.
    metered = regime in ["exploratory", "confirmatory"]
    if metered and updated_session.user_id:
        summary = await run_db(get_usage_summary, str(updated_session.user_id))
        if summary["remaining"] <= 0:
            yield {"type": "text", "content": _limit_message(summary), "regime": "meta", "show_feedback": False}
            return

    raw_result = await _dispatch(regime=regime, message=message, session=updated_session, context=context, recent_messages=recent_messages)

    # A meta turn (e.g. a disambiguation "Quick look / Run a test" button) can
    # hand off to a real analysis regime. Honor that route_to once — re-gating
    # metering for the new regime — instead of dropping it (which previously
    # produced a blank, unsaved reply because route_to was never consumed).
    route_to = raw_result.get("route_to")
    if route_to in ("advisory", "pedagogy", "exploratory", "confirmatory", "orientation") and route_to != regime:
        regime = route_to
        metered = regime in ["exploratory", "confirmatory"]
        if metered and updated_session.user_id:
            summary = await run_db(get_usage_summary, str(updated_session.user_id))
            if summary["remaining"] <= 0:
                yield {"type": "text", "content": _limit_message(summary), "regime": "meta", "show_feedback": False}
                return
        raw_result = await _dispatch(regime=regime, message=message, session=updated_session, context=context, recent_messages=recent_messages)

    # Only charge a metered analysis when real compute happened. The guided
    # assumption-check pause and text-only clarifications set metered=False.
    if metered and updated_session.user_id and raw_result.get("metered", True):
        await run_db(record_usage, str(updated_session.user_id), regime)

    validation = validate_output(regime=regime, response_text=raw_result.get("text", ""), artifact_content=raw_result.get("artifact_content"), has_images=bool(raw_result.get("images")), artifact_type=raw_result.get("artifact_type"))

    if not validation.passed:
        logger.warning("Validation failed for regime=%s: %s", regime, validation.failure_reason)
        yield {"type": "text", "content": get_fallback_message(regime, validation.failure_reason or ""), "regime": regime, "show_feedback": False}
        return

    # Artifact persistence is best-effort: a DB hiccup (or a not-yet-applied
    # migration) must never blank out an answer the user already has in hand.
    artifact_id = None
    try:
        if raw_result.get("artifact_content"):
            artifact = await _log_artifact(raw_result=raw_result, session_id=str(session.id), message_id=source_message_id, regime=regime)
            artifact_id = str(artifact.id) if artifact else None
        elif raw_result.get("code_used"):
            # Preserve mutating/derived code for sandbox replay even when the turn
            # produced no user-facing artifact, so a silent sandbox rebuild can
            # restore session state. Rendered nowhere (unknown type -> no report
            # section, not in the explorer), it exists only for the replay sequence.
            await run_db(
                log_artifact, session_id=str(session.id), stage="data_preparation",
                artifact_type="derived_column", content={"note": "captured for replay"},
                message_id=source_message_id, code_used=raw_result["code_used"], variables_involved=None,
            )
    except Exception as e:
        logger.warning("Artifact persistence failed (continuing without it): %s", e)

    if regime in ("exploratory", "confirmatory"):
        capture_event(_analytics_id(session, updated_session), "analysis_run", {
            "regime": regime,
            "engine_verified": raw_result.get("engine_verified", True),
            "test": raw_result.get("test_display_name"),  # a test name, not data
            "mode": getattr(updated_session, "mode", "explore"),
            "has_chart": bool(raw_result.get("images")),
        })

    new_count = await run_db(increment_feedback_count, str(session.id))
    show_feedback = new_count % FEEDBACK_EVERY_N_TURNS == 0

    for execution in raw_result.get("executions", []):
        yield {"type": "code_execution", "code": execution.get("code", ""), "output": execution.get("output", ""), "regime": regime, "show_feedback": False}

    # Verification badge: tell the UI whether a statistical result came from the
    # verified test library or the LLM-assisted tier.
    if raw_result.get("test_display_name"):
        yield {"type": "verification", "engine_verified": raw_result.get("engine_verified", True), "test_display_name": raw_result.get("test_display_name"), "regime": regime, "show_feedback": False}

    if validation.cleaned_text:
        yield {"type": "text", "content": validation.cleaned_text, "regime": regime, "artifact_id": artifact_id, "show_feedback": show_feedback}

    chart_caption = raw_result.get("chart_caption")
    for image_b64 in raw_result.get("images", []):
        yield {"type": "image", "content": image_b64, "caption": chart_caption, "regime": regime, "show_feedback": False}

    # Deliver a generated report to the frontend (ReportCard). Without this the
    # meta report handler's "download it below" text had nothing below it — the
    # report chunk was never emitted (pre-existing gap).
    if raw_result.get("report"):
        report = raw_result["report"]
        capture_event(_analytics_id(session, updated_session), "report_generated", {
            "artifact_count": report.get("artifact_count"),
            "stages": len(report.get("stages_covered") or []),
            "has_latex": bool(report.get("latex")),
        })
        yield {"type": "report", "report": report, "regime": regime, "show_feedback": False}

    # Nudges are always eligible now (mode replaced the suggestion_mode gate).
    # nudge_style tells the UI to render it directive (guided) or soft (explore).
    if raw_result.get("suggested_next"):
        yield {"type": "guidance_suggestion", "content": raw_result["suggested_next"], "next_action": raw_result.get("next_action"), "nudge_style": raw_result.get("nudge_style", "soft"), "is_hypothesis_candidate": raw_result.get("is_hypothesis_candidate", False), "regime": regime, "show_feedback": False}


def _limit_message(summary: dict[str, Any]) -> str:
    plan = summary.get("plan", "free")
    limit = summary.get("limit", 0)
    return (
        f"You've used all {limit} analyses on your **{plan}** plan this month. "
        "Your limit resets at the start of next month — or upgrade to Pro to keep going now."
    )


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
    if regime == "cleaning":
        return await cleaning.handle(message, session, context)
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

    profile = await run_db(get_cached_profile, session_id)
    if not profile:
        return None

    mentioned_columns = [col for col in profile.get("columns", {}).keys() if col.lower() in message.lower()]
    if len(mentioned_columns) >= 2:
        existing = await run_db(find_similar_artifact, session_id=session_id, stage="exploratory", artifact_type="chart", variables_involved=mentioned_columns)
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
        existing = await run_db(find_similar_artifact, session_id=session_id, stage=stage, artifact_type=artifact_type, variables_involved=variables)
        new_artifact = await run_db(log_artifact, session_id=session_id, stage=stage, artifact_type=artifact_type, content=raw_result.get("artifact_content", {}), message_id=message_id, code_used=raw_result.get("code_used"), variables_involved=variables)
        if existing:
            await run_db(mark_superseded, str(existing.id), str(new_artifact.id))
        return new_artifact

    return await run_db(log_artifact, session_id=session_id, stage=stage, artifact_type=artifact_type, content=raw_result.get("artifact_content", {}), message_id=message_id, code_used=raw_result.get("code_used"), variables_involved=variables)
