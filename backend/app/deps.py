from fastapi import Header, HTTPException
from app.db.sessions import get_session, touch_last_active
from app.db.models import Session


async def get_current_session(x_session_id: str = Header(...)) -> Session:
    session = get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Upload a dataset first to start a session."
        )
    touch_last_active(x_session_id)
    return session
