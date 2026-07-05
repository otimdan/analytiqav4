from fastapi import APIRouter, Depends

from app.auth import get_current_user, AuthUser
from app.db.aio import run_db
from app.db.usage import get_usage_summary

router = APIRouter(prefix="/me", tags=["account"])


@router.get("/usage")
async def my_usage(user: AuthUser = Depends(get_current_user)) -> dict:
    """Current user's plan and this month's analysis usage."""
    return await run_db(get_usage_summary, user.id)
