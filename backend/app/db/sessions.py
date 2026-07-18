from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any

from app.db.supabase_client import get_client
from app.db.models import Session


def create_session(dataset_filename: str, dataset_csv: str, user_id: Optional[str] = None, mode: str = "explore") -> Session:
    client = get_client()
    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    # Mode is fixed at creation and never updated afterward (immutable per task).
    safe_mode = mode if mode in ("explore", "guided") else "explore"
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
    session_row = result.data[0]
    # Best-effort title + mode. Separate updates so a missing column (before
    # migrations 005/006) can't break dataset upload — the task just degrades to
    # an untitled 'explore' task instead of failing.
    updates: dict[str, Any] = {}
    if dataset_filename:
        updates["title"] = dataset_filename
    updates["mode"] = safe_mode
    try:
        client.table("sessions").update(updates).eq("id", session_id).execute()
        session_row = {**session_row, **updates}
    except Exception:
        try:
            client.table("sessions").update({"title": dataset_filename}).eq("id", session_id).execute()
        except Exception:
            pass
    return Session(**session_row)


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


def update_dataset_csv(session_id: str, csv_text: str) -> None:
    # Replace the working dataset with a cleaned/transformed version. This is the
    # durable source of truth (re-mounted on sandbox rebuilds), so cleaning
    # persists without needing code replay.
    client = get_client()
    client.table("sessions").update({"dataset_csv": csv_text}).eq("id", session_id).execute()


def clear_dataset(session_id: str) -> None:
    client = get_client()
    client.table("sessions").update({
        "dataset_csv": None,
        "sandbox_id": None,
    }).eq("id", session_id).execute()


def get_sessions_for_user(user_id: str) -> list[dict[str, Any]]:
    # Lightweight list for the sidebar — deliberately omits dataset_csv (large).
    # dataset_ready lets the UI distinguish resumable tasks from wiped ones.
    client = get_client()
    # NOTE: do NOT list `mode` in an explicit PostgREST select — `mode` is a
    # Postgres ordered-set aggregate, so a bare `mode` token is parsed as the
    # aggregate function and the request 400s. The sidebar doesn't need per-task
    # mode anyway (the active task's mode comes from /state, which uses select=*).
    result = (
        client.table("sessions")
        .select("id, title, dataset_filename, created_at, last_active_at, dataset_csv")
        .eq("user_id", user_id)
        .order("last_active_at", desc=True)
        .execute()
    )
    return [
        {
            "id": row["id"],
            "title": row.get("title") or row.get("dataset_filename") or "Untitled task",
            "dataset_filename": row.get("dataset_filename"),
            "created_at": row.get("created_at"),
            "last_active_at": row.get("last_active_at"),
            "dataset_ready": bool(row.get("dataset_csv")),
        }
        for row in result.data
    ]


def update_title(session_id: str, title: str) -> None:
    client = get_client()
    client.table("sessions").update({"title": title}).eq("id", session_id).execute()


def delete_session(session_id: str) -> None:
    # messages/artifacts/feedback cascade via ON DELETE CASCADE (migration 001).
    client = get_client()
    client.table("sessions").delete().eq("id", session_id).execute()
