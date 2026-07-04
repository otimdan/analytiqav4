from fastapi import APIRouter, Depends, HTTPException
from app.db.models import Session, FeedbackRequest
from app.db.feedback import record_rating
from app.db.aio import run_db
from app.deps import get_current_session

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
async def submit_feedback(req: FeedbackRequest, session: Session = Depends(get_current_session)) -> dict:
    try:
        feedback = await run_db(record_rating, session_id=str(session.id), message_id=req.message_id, rating=req.rating, comment=req.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "feedback_id": str(feedback.id)}
