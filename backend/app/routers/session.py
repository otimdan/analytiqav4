from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from app.db.models import Session, UploadResponse, SessionStateResponse
from app.db.sessions import (
    get_session, create_session as db_create_session,
    get_sessions_for_user, update_title, delete_session as db_delete_session,
)
from app.db.artifacts import get_artifacts_for_session
from app.db.aio import run_db
from app.deps import get_current_session
from app.auth import get_current_user, AuthUser
from app.rate_limit import upload_limiter
from app.profiling.profiler import build_profile
from app.profiling.cache import set_cached_profile
from app.sandbox.manager import get_or_create_sandbox, terminate_sandbox
from app.orchestrator.hypothesis_watcher import get_first_message
from app.db.supabase_client import get_client
from app.ingest.encoding import decode_csv
from app.ingest.headers import strip_header_bands
from app.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MESSAGE

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    mode: str = Form("explore"),
    user: AuthUser = Depends(get_current_user),
) -> UploadResponse:
    if not upload_limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many uploads in a short time. Please wait a moment.")
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    # Task mode is chosen up front (mode picker) and fixed at creation.
    if mode not in ("explore", "guided"):
        mode = "explore"

    # Reject before read(): read() pulls the whole upload into memory, and the
    # decoded text plus the line list below are alive at the same time, so an
    # unbounded file can OOM the web process. Starlette leaves .size unset for
    # some clients, hence the second check against the bytes actually read.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=MAX_UPLOAD_MESSAGE)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=MAX_UPLOAD_MESSAGE)

    ingest_notes: list[str] = []
    try:
        decoded = decode_csv(content)
    except ValueError:
        raise HTTPException(status_code=400, detail="Could not read the file. Make sure it's a plain text CSV.")

    if not decoded.certain:
        ingest_notes.append(
            f"This file isn't UTF-8, so its encoding was inferred as {decoded.encoding}. "
            "Check that accented characters, dashes and symbols look right."
        )

    csv_text, bands_dropped = strip_header_bands(decoded.text)
    if bands_dropped:
        ingest_notes.append(
            f"Dropped {bands_dropped} merged-cell section row{'s' if bands_dropped > 1 else ''} "
            "above the column names, so the real headers are used."
        )

    lines = [l for l in csv_text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="The file appears to be empty or has only headers.")

    session = await run_db(db_create_session, dataset_filename=file.filename, dataset_csv=csv_text, user_id=user.id, mode=mode)
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
        ingest_notes=ingest_notes,
    )


@router.get("/list")
async def list_sessions(user: AuthUser = Depends(get_current_user)) -> list[dict]:
    # The user's tasks for the sidebar, most-recently-active first.
    return await run_db(get_sessions_for_user, user.id)


class RenameRequest(BaseModel):
    title: str


@router.post("/{session_id}/title")
async def rename_session(session_id: str, req: RenameRequest, session: Session = Depends(get_current_session)) -> dict:
    title = req.title.strip()[:120]
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    await run_db(update_title, str(session.id), title)
    return {"ok": True, "title": title}


@router.post("/{session_id}/delete")
async def delete_session(session_id: str, session: Session = Depends(get_current_session)) -> dict:
    # Ownership verified by get_current_session. Free the sandbox, then delete the
    # task (messages/artifacts/feedback cascade).
    owned_id = str(session.id)
    await terminate_sandbox(owned_id)
    await run_db(db_delete_session, owned_id)
    return {"ok": True}


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str, user: AuthUser = Depends(get_current_user)) -> SessionStateResponse:
    session = await run_db(get_session, session_id)
    if not session or str(session.user_id) != user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    artifacts = await run_db(get_artifacts_for_session, session_id, include_superseded=False)
    profile = session.profile
    profile_summary = None
    if profile:
        profile_summary = {"row_count": profile.get("row_count"), "column_count": profile.get("column_count"), "summary": profile.get("summary", "")}

    return SessionStateResponse(
        session_id=session_id,
        mode=getattr(session, "mode", "explore"),
        hypothesis_text=session.hypothesis_text,
        dataset_filename=session.dataset_filename,
        profile_summary=profile_summary,
        artifact_count=len(artifacts),
        dataset_ready=bool(session.dataset_csv),
    )


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, user: AuthUser = Depends(get_current_user)) -> list[dict]:
    session = await run_db(get_session, session_id)
    if not session or str(session.user_id) != user.id:
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
            "images": row.get("images") or [],
            "created_at": row.get("created_at"),
        })
    return messages


@router.post("/{session_id}/close")
async def close_session(session_id: str) -> dict:
    # Intentionally unauthenticated: called via navigator.sendBeacon on page
    # unload, which cannot attach an Authorization header. It only releases a
    # sandbox handle keyed by an unguessable UUID.
    session = await run_db(get_session, session_id)
    if session:
        await terminate_sandbox(session_id)
    return {"ok": True}


@router.post("/{session_id}/reset")
async def reset_conversation(session_id: str, session: Session = Depends(get_current_session)) -> dict:
    # Operate on the verified-owned session (from get_current_session), not the
    # raw path param, so a caller can't reset a session they don't own.
    owned_id = str(session.id)
    await run_db(lambda: get_client().table("messages").delete().eq("session_id", owned_id).execute())
    first_message = await run_db(get_first_message, session)
    await run_db(lambda: get_client().table("messages").insert({
        "session_id": owned_id, "role": "assistant",
        "content": first_message, "regime": "meta", "classification_confidence": "rule_based",
    }).execute())
    return {"ok": True}
