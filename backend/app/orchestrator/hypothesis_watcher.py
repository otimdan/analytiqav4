import re
from typing import Any
from app.db.models import Session, Message
from app.db.sessions import store_hypothesis, update_flags
from app.db.hypothesis_candidates import create_candidate, get_pending_candidate, accept_candidate, decline_candidate
from app.hypothesis.intake import extract_hypothesis, match_variables_to_columns
from app.profiling.cache import get_cached_profile

FIRST_AI_MESSAGE = "Loaded {rows} rows and {columns} columns from {filename}. What are you trying to find out — or are you just exploring for now?"


def get_first_message(session) -> str:
    profile = get_cached_profile(str(session.id))
    rows = profile.get("row_count", "?") if profile else "?"
    cols = profile.get("column_count", "?") if profile else "?"
    return FIRST_AI_MESSAGE.format(rows=rows, columns=cols, filename=session.dataset_filename or "your dataset")


async def check_message_for_hypothesis(message: str, session: Session, source_message_id: str, is_first_reply: bool = False) -> dict[str, Any]:
    profile = get_cached_profile(str(session.id))
    if not profile:
        return {"action": "none", "confirm_prompt": None, "hypothesis_text": None}

    if is_first_reply:
        extraction = await extract_hypothesis(message)
        if not extraction.is_hypothesis:
            if _sounds_like_help_request(message):
                update_flags(str(session.id), suggestion_mode=True)
                return {"action": "suggestion_mode_only", "confirm_prompt": None, "hypothesis_text": None}
            return {"action": "none", "confirm_prompt": None, "hypothesis_text": None}

        matched, unmatched = match_variables_to_columns(extraction.named_variables, list(profile.get("columns", {}).keys()))
        if unmatched:
            create_candidate(str(session.id), extraction.research_question or message, source_message_id, matched_columns=matched)
            confirm_prompt = _build_column_mismatch_prompt(extraction.research_question or message, unmatched, list(profile.get("columns", {}).keys()))
            return {"action": "candidate_created", "confirm_prompt": confirm_prompt, "hypothesis_text": extraction.research_question}

        store_hypothesis(str(session.id), extraction.research_question or message, matched)
        return {"action": "committed", "confirm_prompt": None, "hypothesis_text": extraction.research_question}

    extraction = await extract_hypothesis(message)
    if not extraction.is_hypothesis:
        return {"action": "none", "confirm_prompt": None, "hypothesis_text": None}

    matched, _ = match_variables_to_columns(extraction.named_variables, list(profile.get("columns", {}).keys()))
    create_candidate(str(session.id), extraction.research_question or message, source_message_id, matched_columns=matched)
    confirm_prompt = (
        f"That sounds like a research question — want me to track this as a project and show your progress on the left as you go?\n\n"
        f"**[Track as project]** · **[No, just answer this]**"
    )
    return {"action": "candidate_created", "confirm_prompt": confirm_prompt, "hypothesis_text": extraction.research_question}


async def handle_accept(session_id: str) -> bool:
    candidate = get_pending_candidate(session_id)
    if not candidate:
        return False
    columns = candidate.matched_columns or []
    store_hypothesis(session_id, candidate.candidate_text, columns)
    accept_candidate(str(candidate.id))
    return True


async def handle_decline(session_id: str) -> None:
    candidate = get_pending_candidate(session_id)
    if candidate:
        decline_candidate(str(candidate.id))


def check_orientation_trigger(message: str) -> bool:
    return _sounds_like_help_request(message)


def _sounds_like_help_request(message: str) -> bool:
    help_patterns = [
        r"\bhelp me\b", r"\bi don'?t know what to do\b",
        r"\bi'?m (not sure|stuck|lost)\b", r"\bwhat (should|do) i do\b",
        r"\bguide me\b", r"\bjust exploring\b", r"\bnot sure (yet|what)\b",
    ]
    message_lower = message.lower()
    return any(re.search(p, message_lower) for p in help_patterns)


def _build_column_mismatch_prompt(hypothesis_text: str, unmatched: list[str], available_columns: list[str]) -> str:
    unmatched_str = ", ".join(f"'{v}'" for v in unmatched)
    available_str = ", ".join(f"`{c}`" for c in available_columns[:12])
    return (
        f"I found your research question but couldn't match {unmatched_str} to a column in your dataset.\n\n"
        f"Available columns: {available_str}\n\nWhich column did you mean?"
    )
