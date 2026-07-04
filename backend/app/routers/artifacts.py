from fastapi import APIRouter, Depends
from app.db.models import Session
from app.db.artifacts import get_artifacts_for_session, get_completed_stages
from app.deps import get_current_session

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{session_id}")
async def list_artifacts(session_id: str, session: Session = Depends(get_current_session)) -> list:
    artifacts = get_artifacts_for_session(session_id, include_superseded=False)
    return [
        {
            "id": str(a.id),
            "session_id": str(a.session_id),
            "message_id": str(a.message_id) if a.message_id else None,
            "created_at": str(a.created_at),
            "stage": a.stage,
            "artifact_type": a.artifact_type,
            "content": a.content,
            "code_used": a.code_used,
            "superseded": a.superseded,
            "superseded_by": str(a.superseded_by) if a.superseded_by else None,
            "variables_involved": a.variables_involved,
        }
        for a in artifacts
    ]


@router.get("/{session_id}/stages")
async def list_completed_stages(session_id: str, session: Session = Depends(get_current_session)) -> list[str]:
    return get_completed_stages(session_id)
