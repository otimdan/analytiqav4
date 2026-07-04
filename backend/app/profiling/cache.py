from typing import Any, Optional
from app.db.sessions import get_session, update_profile


def get_cached_profile(session_id: str) -> Optional[dict[str, Any]]:
    session = get_session(session_id)
    if not session or not session.profile:
        return None
    return session.profile


def set_cached_profile(session_id: str, profile: dict[str, Any]) -> None:
    update_profile(session_id, profile)


def profile_is_ready(session_id: str) -> bool:
    session = get_session(session_id)
    return bool(session and session.profile)
