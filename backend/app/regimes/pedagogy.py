from typing import Any
from app.llm.fireworks_client import call_main_model
from app.config import FIREWORKS_MODEL_CHAT
from app.llm.prompts import PEDAGOGY_SYSTEM_PROMPT


async def handle(message: str, context: dict[str, Any]) -> dict[str, Any]:
    response = await call_main_model(messages=[{"role": "user", "content": message}], system_prompt=PEDAGOGY_SYSTEM_PROMPT, tools=None, temperature=0.2, model=FIREWORKS_MODEL_CHAT)
    text = response.message.content or ""
    # Offer to ground the concept in the user's data. Directive in guided mode,
    # soft in explore; always eligible now (no suggestion_mode gate).
    suggested_next = None
    nudge_style = "soft"
    if context.get("profile_summary"):
        suggested_next = "Want to see how this applies to your dataset?"
        if context.get("mode") == "guided":
            nudge_style = "directive"
    return {"text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": suggested_next, "nudge_style": nudge_style, "is_hypothesis_candidate": False}
