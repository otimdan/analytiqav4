from typing import Any
from app.llm.fireworks_client import call_main_model
from app.llm.prompts import PEDAGOGY_SYSTEM_PROMPT


async def handle(message: str, context: dict[str, Any]) -> dict[str, Any]:
    response = await call_main_model(messages=[{"role": "user", "content": message}], system_prompt=PEDAGOGY_SYSTEM_PROMPT, tools=None, temperature=0.2)
    text = response.message.content or ""
    suggested_next = None
    if context.get("suggestion_mode") and context.get("profile_summary"):
        suggested_next = "Want to see how this applies to your dataset?"
    return {"text": text, "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": suggested_next, "is_hypothesis_candidate": False}
