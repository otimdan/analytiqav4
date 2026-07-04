import re
from typing import Any
from app.db.models import Session
from app.orchestrator.hypothesis_watcher import handle_accept, handle_decline
from app.reports.generator import generate_report


async def handle(message: str, session: Session, context: dict[str, Any]) -> dict[str, Any]:
    message_lower = message.strip().lower()

    if _is_acceptance(message_lower):
        return await _handle_accept(session)
    if _is_decline(message_lower):
        return await _handle_decline(session)
    if _is_quick_look(message_lower):
        return _routing_result("exploratory")
    if _is_run_test(message_lower):
        return _routing_result("confirmatory")
    if _is_report_request(message):
        return await _handle_report(session)
    if _is_acknowledgment(message_lower):
        return _acknowledge()
    if _is_challenge(message_lower):
        return await _handle_challenge(session, context)
    if _is_navigation(message_lower):
        return _navigate()

    return _empty_result("Got it — what would you like to do next?")


async def _handle_accept(session: Session) -> dict[str, Any]:
    committed = await handle_accept(str(session.id))
    if committed:
        return _empty_result("Great — I've saved your research question and turned on progress tracking on the left. Let's keep going.")
    return _empty_result("I couldn't find a pending research question to track. State your research question and I'll pick it up.")


async def _handle_decline(session: Session) -> dict[str, Any]:
    await handle_decline(str(session.id))
    return _empty_result("No problem — I'll just answer this one directly.")


def _routing_result(target_regime: str) -> dict[str, Any]:
    return {"text": "", "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False, "route_to": target_regime}


async def _handle_report(session: Session) -> dict[str, Any]:
    try:
        report_result = await generate_report(str(session.id))
        return {"text": "Your report is ready — download it below.", "images": [], "artifact_content": None, "artifact_type": "report", "stage": None, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False, "report": report_result}
    except Exception:
        return _empty_result("I had trouble generating the report. Make sure you have some completed analyses first.")


async def _handle_challenge(session: Session, context: dict[str, Any]) -> dict[str, Any]:
    from app.db.artifacts import get_artifacts_for_session
    from app.db.aio import run_db
    artifacts = await run_db(get_artifacts_for_session, str(session.id), include_superseded=False)
    inferential = [a for a in reversed(artifacts) if a.stage == "inferential"]
    if not inferential:
        return _empty_result("I don't have a recent statistical result to review. What specifically looks wrong?")
    last = inferential[0]
    content = last.content or {}
    test_name = content.get("display_name", "the test")
    reasoning = content.get("reasoning", "")
    suspect = content.get("suspect_result", False)
    if suspect:
        return _empty_result(f"You're right to question it — I flagged a concern with that result too: {content.get('suspect_reason', '')}. Want me to re-run it with a different approach?")
    elif reasoning:
        return _empty_result(f"Here's why I used {test_name}: {reasoning}. If you think the data warrants a different test, tell me which one and I'll run both so you can compare.")
    return _empty_result(f"I used {test_name} for this analysis. What specifically looks incorrect? Tell me and I'll re-examine it.")


def _acknowledge() -> dict[str, Any]:
    return _empty_result("Glad to help — what would you like to look at next?")


def _navigate() -> dict[str, Any]:
    return {"text": "", "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False, "frontend_action": "navigate_back"}


def _is_acceptance(msg): return bool(re.search(r"^(yes|yeah|yep|sure|ok|okay|go ahead|do it|track it|yes please|let'?s do it|yes[,.]?\s*(track it|do it|go ahead|proceed))", msg, re.IGNORECASE))
def _is_decline(msg): return bool(re.search(r"^(no|nope|don'?t|skip|just answer|no thanks|not now|not yet|no[,.]?\s*(just answer|don'?t track|skip))", msg, re.IGNORECASE))
def _is_quick_look(msg): return "quick look" in msg or "just look" in msg
def _is_run_test(msg): return "run a test" in msg or "run test" in msg
def _is_report_request(msg): return bool(re.search(r"\b(generate|create|make|give me|produce|write)\b.{0,30}\b(report|summary|writeup|write.up|document)\b", msg, re.IGNORECASE))
def _is_acknowledgment(msg): return bool(re.search(r"^(thanks?|thank you|ok(ay)?|great|nice|perfect|i like (that|it)|good|cool|awesome|sawa|webale|asante|nzuri|poa)[!.]?\s*$", msg, re.IGNORECASE))
def _is_challenge(msg): return bool(re.search(r"\b(you'?re wrong|that'?s (not right|incorrect|wrong)|i (don'?t|do not) (think|believe) (that'?s|this is) (right|correct)|that doesn'?t (seem|look|sound) right|are you sure|i disagree)\b", msg, re.IGNORECASE))
def _is_navigation(msg): return bool(re.search(r"^(go back|undo|start over|reset|clear|restart|redo|previous step|back to)\b", msg, re.IGNORECASE))
def _empty_result(text): return {"text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": None, "is_hypothesis_candidate": False}
