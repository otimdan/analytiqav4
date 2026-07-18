from typing import Any
from app.db.models import Session
from app.llm.fireworks_client import call_structured_output
from app.config import FIREWORKS_MODEL_CHAT
from app.llm.prompts import ORIENTATION_SYSTEM_PROMPT
from app.llm.schemas import OrientationRecap
from app.db.artifacts import get_artifacts_for_session
from app.orchestrator.context_builder import format_context_for_prompt


async def handle(session: Session, context: dict[str, Any]) -> dict[str, Any]:
    artifacts = get_artifacts_for_session(str(session.id), include_superseded=False)
    completed_descriptions = []
    for artifact in artifacts:
        if artifact.artifact_type == "test_result":
            content = artifact.content or {}
            test = content.get("display_name", "test")
            variables = artifact.variables_involved or []
            p = content.get("p_value")
            desc = f"{test} on {' vs '.join(variables)}"
            if p is not None: desc += f" (p={p:.3f})"
            completed_descriptions.append(desc)
        elif artifact.artifact_type == "chart":
            variables = artifact.variables_involved or []
            completed_descriptions.append(f"Chart of {' vs '.join(variables)}")
        elif artifact.artifact_type == "cleaned_dataset":
            content = artifact.content or {}
            ops = content.get("operations_applied", [])
            if ops: completed_descriptions.append(f"Data cleaning: {', '.join(ops)}")

    context_block = format_context_for_prompt(context)
    orientation_prompt = (
        f"{context_block}\n\n"
        f"What has been done so far:\n"
        + ("\n".join(f"- {d}" for d in completed_descriptions) if completed_descriptions else "- Nothing yet")
        + "\n\nGive a brief recap and one specific next step."
    )

    recap: OrientationRecap = await call_structured_output(messages=[{"role": "user", "content": orientation_prompt}], system_prompt=ORIENTATION_SYSTEM_PROMPT, schema_class=OrientationRecap, temperature=0.2, model=FIREWORKS_MODEL_CHAT)

    done_text = ""
    if recap.what_has_been_done:
        items = "\n".join(f"- {item}" for item in recap.what_has_been_done)
        done_text = f"Here's where you are:\n{items}\n\n"

    response_text = f"{done_text}**Next step:** {recap.suggested_next}"

    next_action = None
    if recap.next_step_query:
        next_action = {"label": "Run it", "query": recap.next_step_query}

    nudge_style = "directive" if context.get("mode") == "guided" else "soft"

    return {"text": response_text, "images": [], "artifact_content": None, "artifact_type": None, "stage": None, "variables_involved": None, "code_used": None, "suggested_next": recap.suggested_next, "next_action": next_action, "nudge_style": nudge_style, "is_hypothesis_candidate": recap.is_hypothesis_candidate}
