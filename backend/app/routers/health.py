from fastapi import APIRouter
from app.config import FIREWORKS_MODEL_MAIN, FIREWORKS_MODEL_CLASSIFIER

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "main_model": FIREWORKS_MODEL_MAIN, "classifier_model": FIREWORKS_MODEL_CLASSIFIER}
