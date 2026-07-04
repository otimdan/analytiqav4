from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.db.models import Session, UploadResponse, SessionStateResponse
from app.db.sessions import get_session, create_session as db_create_session
from app.db.artifacts import get_artifacts_for_session
from app.db.aio import run_db
from app.deps import get_current_session
from app.profiling.profiler import build_profile
from app.profiling.cache import set_cached_profile
from app.sandbox.manager import get_or_create_sandbox, terminate_sandbox
from app.orchestrator.hypothesis_watcher import get_first_message
from app.db.supabase_client import get_client

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the file. Make sure it's a plain CSV (UTF-8 or Latin-1 encoding).")

    lines = [l for l in csv_text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="The file appears to be empty or has only headers.")

    session = await run_db(db_create_session, dataset_filename=file.filename, dataset_csv=csv_text)
    sbx = await get_or_create_sandbox(str(session.id))

    try:
        profile = await build_profile(sbx, str(session.id))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Dataset profiling failed: {str(e)}")

    await run_db(set_cached_profile, str(session.id), profile)

    first_message = await run_db(get_first_message, session)
    await run_db(lambda: get_client().table("messages").insert({
        "session_id": str(session.id),
        "role": "assistant",
        "content": first_message,
        "regime": "meta",
        "classification_confidence": "rule_based",
    }).execute())

    cols = lines[0].split(",")
    col_names = [c.strip().strip('"') for c in cols[:12]]

    return UploadResponse(
        session_id=str(session.id),
        filename=file.filename,
        rows=len(lines) - 1,
        columns=len(cols),
        column_names=col_names,
        profile_summary={"row_count": profile.get("row_count"), "column_count": profile.get("column_count"), "summary": profile.get("summary", "")},
    )


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str) -> SessionStateResponse:
    session = await run_db(get_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    artifacts = await run_db(get_artifacts_for_session, session_id, include_superseded=False)
    profile = session.profile
    profile_summary = None
    if profile:
        profile_summary = {"row_count": profile.get("row_count"), "column_count": profile.get("column_count"), "summary": profile.get("summary", "")}

    return SessionStateResponse(
        session_id=session_id,
        hypothesis_on_record=session.hypothesis_on_record,
        suggestion_mode=session.suggestion_mode,
        hypothesis_text=session.hypothesis_text,
        dataset_filename=session.dataset_filename,
        profile_summary=profile_summary,
        artifact_count=len(artifacts),
        dataset_ready=bool(session.dataset_csv),
    )


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str) -> list[dict]:
    session = await run_db(get_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    result = await run_db(lambda: (
        get_client().table("messages").select("*")
        .eq("session_id", session_id).order("created_at", desc=False).execute()
    ))
    messages = []
    for row in result.data:
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "regime": row.get("regime"),
            "executions": row.get("executions") or [],
            "created_at": row.get("created_at"),
        })
    return messages


@router.post("/{session_id}/close")
async def close_session(session_id: str) -> dict:
    session = await run_db(get_session, session_id)
    if session:
        await terminate_sandbox(session_id)
    return {"ok": True}


@router.post("/{session_id}/reset")
async def reset_conversation(session_id: str, session: Session = Depends(get_current_session)) -> dict:
    await run_db(lambda: get_client().table("messages").delete().eq("session_id", session_id).execute())
    first_message = await run_db(get_first_message, session)
    await run_db(lambda: get_client().table("messages").insert({
        "session_id": session_id, "role": "assistant",
        "content": first_message, "regime": "meta", "classification_confidence": "rule_based",
    }).execute())
    return {"ok": True}
