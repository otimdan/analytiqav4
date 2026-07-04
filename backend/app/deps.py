from fastapi import Header, HTTPException, Depends
from app.db.sessions import get_session, touch_last_active
from app.db.aio import run_db
from app.db.models import Session
from app.auth import get_current_user, AuthUser


async def get_current_session(
    x_session_id: str = Header(...),
    user: AuthUser = Depends(get_current_user),
) -> Session:
    session = await run_db(get_session, x_session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Session not found. Upload a dataset first to start a session."
        )
    if str(session.user_id) != user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this session.")
    await run_db(touch_last_active, x_session_id)
    return session
