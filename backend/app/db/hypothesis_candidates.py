from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import get_client
from app.db.models import HypothesisCandidate


def create_candidate(
    session_id: str,
    candidate_text: str,
    source_message_id: str,
    matched_columns: Optional[list[str]] = None,
) -> HypothesisCandidate:
    decline_pending_candidate(session_id)
    client = get_client()
    row = {
        "id": str(uuid4()),
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_text": candidate_text,
        "matched_columns": matched_columns,
        "source_message_id": source_message_id,
        "status": "pending",
    }
    result = client.table("hypothesis_candidates").insert(row).execute()
    return HypothesisCandidate(**result.data[0])


def get_pending_candidate(session_id: str) -> Optional[HypothesisCandidate]:
    client = get_client()
    result = (
        client.table("hypothesis_candidates")
        .select("*")
        .eq("session_id", session_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return HypothesisCandidate(**result.data[0])


def accept_candidate(candidate_id: str) -> None:
    client = get_client()
    client.table("hypothesis_candidates").update({"status": "accepted"}).eq("id", candidate_id).execute()


def decline_candidate(candidate_id: str) -> None:
    client = get_client()
    client.table("hypothesis_candidates").update({"status": "declined"}).eq("id", candidate_id).execute()


def decline_pending_candidate(session_id: str) -> None:
    client = get_client()
    client.table("hypothesis_candidates").update({"status": "declined"}).eq("session_id", session_id).eq("status", "pending").execute()
