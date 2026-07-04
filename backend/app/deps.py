from fastapi import Header, HTTPException
from app.db.sessions import get_session, touch_last_active
from app.db.aio import run_db
from app.db.models import Session


async def get_current_session(x_session_id: str = Header(...)) -> Session:
    session = await run_db(get_session, x_session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Upload a dataset first to start a session."
        )
    await run_db(touch_last_active, x_session_id)
    return session
