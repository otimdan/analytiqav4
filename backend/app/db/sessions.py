from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any

from app.db.supabase_client import get_client
from app.db.models import Session


def create_session(dataset_filename: str, dataset_csv: str, user_id: Optional[str] = None) -> Session:
    client = get_client()
    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    row = {
        "id": session_id,
        "user_id": user_id,
        "created_at": now.isoformat(),
        "last_active_at": now.isoformat(),
        "dataset_filename": dataset_filename,
        "dataset_csv": dataset_csv,
        "sandbox_id": None,
        "profile": None,
        "hypothesis_text": None,
        "hypothesis_columns": None,
        "pending_candidate": None,
        "hypothesis_on_record": False,
        "suggestion_mode": False,
        "feedback_count": 0,
    }
    result = client.table("sessions").insert(row).execute()
    return Session(**result.data[0])


def get_session(session_id: str) -> Optional[Session]:
    client = get_client()
    result = client.table("sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        return None
    return Session(**result.data)


def update_sandbox_id(session_id: str, sandbox_id: str) -> None:
    client = get_client()
    client.table("sessions").update({"sandbox_id": sandbox_id}).eq("id", session_id).execute()


def update_profile(session_id: str, profile: dict[str, Any]) -> None:
    client = get_client()
    client.table("sessions").update({"profile": profile}).eq("id", session_id).execute()


def update_flags(
    session_id: str,
    hypothesis_on_record: Optional[bool] = None,
    suggestion_mode: Optional[bool] = None,
) -> None:
    client = get_client()
    updates: dict[str, Any] = {}
    if hypothesis_on_record is not None:
        updates["hypothesis_on_record"] = hypothesis_on_record
    if suggestion_mode is not None:
        updates["suggestion_mode"] = suggestion_mode
    if updates:
        client.table("sessions").update(updates).eq("id", session_id).execute()


def store_hypothesis(session_id: str, hypothesis_text: str, matched_columns: list[str]) -> None:
    client = get_client()
    client.table("sessions").update({
        "hypothesis_text": hypothesis_text,
        "hypothesis_columns": matched_columns,
        "hypothesis_on_record": True,
        "suggestion_mode": True,
    }).eq("id", session_id).execute()


def touch_last_active(session_id: str) -> None:
    client = get_client()
    client.table("sessions").update({
        "last_active_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", session_id).execute()


def increment_feedback_count(session_id: str) -> int:
    client = get_client()
    session = get_session(session_id)
    if not session:
        return 0
    new_count = session.feedback_count + 1
    client.table("sessions").update({"feedback_count": new_count}).eq("id", session_id).execute()
    return new_count


def clear_sandbox_id(session_id: str) -> None:
    # Free the E2B sandbox but keep dataset_csv as the durable source of truth,
    # so the session can be resumed (data re-mounted) on the next request.
    client = get_client()
    client.table("sessions").update({
        "sandbox_id": None,
    }).eq("id", session_id).execute()


def clear_dataset(session_id: str) -> None:
    client = get_client()
    client.table("sessions").update({
        "dataset_csv": None,
        "sandbox_id": None,
    }).eq("id", session_id).execute()
