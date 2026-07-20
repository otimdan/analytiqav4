from typing import Any
from app.db.models import Session, Message
from app.db.sessions import store_hypothesis
from app.db.hypothesis_candidates import create_candidate, get_pending_candidate, accept_candidate, decline_candidate
from app.db.aio import run_db
from app.hypothesis.intake import extract_hypothesis, match_variables_to_columns
from app.profiling.cache import get_cached_profile

FIRST_AI_MESSAGE = "Loaded {rows} rows and {columns} columns from {filename}. What are you trying to find out — or are you just exploring for now?"


def get_first_message(session) -> str:
    profile = get_cached_profile(str(session.id))
    rows = profile.get("row_count", "?") if profile else "?"
    cols = profile.get("column_count", "?") if profile else "?"
    return FIRST_AI_MESSAGE.format(rows=rows, columns=cols, filename=session.dataset_filename or "your dataset")


async def check_message_for_hypothesis(message: str, session: Session, source_message_id: str, is_first_reply: bool = False, mode: str = "explore") -> dict[str, Any]:
    """Silently record the research question in GUIDED mode; do nothing in EXPLORE.

    With explicit modes, the project is tracked from the start in guided mode
    (by virtue of the mode itself), so we never ask "track this as a project?".
    This watcher's only remaining job is to *populate* the research-question text
    when the guided user states it, so the project header can show it. In explore
    mode we never track anything. It never interrupts the answer either way.
    """
    none = {"action": "none", "hypothesis_text": None}

    # Explore mode never tracks a project.
    if mode != "guided":
        return none

    profile = await run_db(get_cached_profile, str(session.id))
    if not profile:
        return none

    # Only capture the question once, on the first reply — don't keep re-writing
    # it mid-conversation.
    if not is_first_reply:
        return none

    extraction = await extract_hypothesis(message)
    if not extraction.is_hypothesis:
        return none

    matched, unmatched = match_variables_to_columns(extraction.named_variables, list(profile.get("columns", {}).keys()))
    # Record the question when it maps cleanly onto real columns; otherwise leave
    # the header blank rather than blocking with a clarifying prompt.
    if matched and not unmatched:
        await run_db(store_hypothesis, str(session.id), extraction.research_question or message, matched)
        return {"action": "committed", "hypothesis_text": extraction.research_question}
    return none


async def handle_accept(session_id: str) -> bool:
    candidate = await run_db(get_pending_candidate, session_id)
    if not candidate:
        return False
    columns = candidate.matched_columns or []
    await run_db(store_hypothesis, session_id, candidate.candidate_text, columns)
    await run_db(accept_candidate, str(candidate.id))
    return True


async def handle_decline(session_id: str) -> None:
    candidate = await run_db(get_pending_candidate, session_id)
    if candidate:
        await run_db(decline_candidate, str(candidate.id))




def _build_column_mismatch_prompt(hypothesis_text: str, unmatched: list[str], available_columns: list[str]) -> str:
    unmatched_str = ", ".join(f"'{v}'" for v in unmatched)
    available_str = ", ".join(f"`{c}`" for c in available_columns[:12])
    return (
        f"I found your research question but couldn't match {unmatched_str} to a column in your dataset.\n\n"
        f"Available columns: {available_str}\n\nWhich column did you mean?"
    )
