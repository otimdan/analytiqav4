from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any

from app.db.supabase_client import get_client
from app.db.models import Artifact


def log_artifact(
    session_id: str,
    stage: str,
    artifact_type: str,
    content: dict[str, Any],
    message_id: Optional[str] = None,
    code_used: Optional[str] = None,
    variables_involved: Optional[list[str]] = None,
) -> Artifact:
    client = get_client()
    now = datetime.now(timezone.utc)
    artifact_id = str(uuid4())
    row = {
        "id": artifact_id,
        "session_id": session_id,
        "message_id": message_id,
        "created_at": now.isoformat(),
        "stage": stage,
        "artifact_type": artifact_type,
        "content": content,
        "code_used": code_used,
        "superseded": False,
        "superseded_by": None,
        "variables_involved": variables_involved,
    }
    result = client.table("artifacts").insert(row).execute()
    return Artifact(**result.data[0])


def get_artifacts_for_session(session_id: str, include_superseded: bool = False) -> list[Artifact]:
    client = get_client()
    query = client.table("artifacts").select("*").eq("session_id", session_id).order("created_at", desc=False)
    if not include_superseded:
        query = query.eq("superseded", False)
    result = query.execute()
    return [Artifact(**row) for row in result.data]


def get_artifacts_by_stage(session_id: str, stage: str) -> list[Artifact]:
    client = get_client()
    result = client.table("artifacts").select("*").eq("session_id", session_id).eq("stage", stage).eq("superseded", False).execute()
    return [Artifact(**row) for row in result.data]


def get_completed_stages(session_id: str) -> list[str]:
    client = get_client()
    result = client.table("artifacts").select("stage").eq("session_id", session_id).eq("superseded", False).execute()
    return list({row["stage"] for row in result.data})


def get_code_replay_sequence(session_id: str) -> list[str]:
    client = get_client()
    result = (
        client.table("artifacts")
        .select("code_used, created_at")
        .eq("session_id", session_id)
        .not_.is_("code_used", "null")
        .order("created_at", desc=False)
        .execute()
    )
    return [row["code_used"] for row in result.data]


def mark_superseded(old_artifact_id: str, new_artifact_id: str) -> None:
    client = get_client()
    client.table("artifacts").update({
        "superseded": True,
        "superseded_by": new_artifact_id,
    }).eq("id", old_artifact_id).execute()


def find_similar_artifact(
    session_id: str,
    stage: str,
    artifact_type: str,
    variables_involved: list[str],
) -> Optional[Artifact]:
    client = get_client()
    result = (
        client.table("artifacts")
        .select("*")
        .eq("session_id", session_id)
        .eq("stage", stage)
        .eq("artifact_type", artifact_type)
        .eq("superseded", False)
        .execute()
    )
    target = sorted(variables_involved)
    for row in result.data:
        existing_vars = sorted(row.get("variables_involved") or [])
        if existing_vars == target:
            return Artifact(**row)
    return None
