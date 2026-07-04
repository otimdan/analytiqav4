from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import get_client
from app.db.models import Feedback


def _coerce_uuid(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        # Client-generated correlation ids (optimistic UI ids) aren't UUIDs;
        # store null rather than 500-ing the whole request on a type error.
        return None


def record_rating(session_id: str, message_id: str, rating: int, comment: Optional[str] = None) -> Feedback:
    if rating < 1 or rating > 5:
        raise ValueError(f"Rating must be between 1 and 5, got {rating}")
    client = get_client()
    now = datetime.now(timezone.utc)
    row = {
        "id": str(uuid4()),
        "session_id": session_id,
        "message_id": _coerce_uuid(message_id),
        "created_at": now.isoformat(),
        "rating": rating,
        "comment": comment,
    }
    result = client.table("feedback").insert(row).execute()
    return Feedback(**result.data[0])


def get_session_ratings(session_id: str) -> list[Feedback]:
    client = get_client()
    result = client.table("feedback").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
    return [Feedback(**row) for row in result.data]
