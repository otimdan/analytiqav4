import json
from typing import Any
from openai import AsyncOpenAI
from app.config import FIREWORKS_API_KEY, FIREWORKS_BASE_URL, FIREWORKS_MODEL_MAIN, FIREWORKS_MODEL_CLASSIFIER, TOKEN_LIMIT
from app.llm.schemas import ClassificationResult

_client = AsyncOpenAI(api_key=FIREWORKS_API_KEY, base_url=FIREWORKS_BASE_URL)


async def call_main_model(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": FIREWORKS_MODEL_MAIN,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Fireworks rejects `tools: null` — omit the field entirely when there are
    # no tools (non-tool regimes like advisory/pedagogy) rather than sending None.
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    response = await _client.chat.completions.create(**kwargs)
    return response.choices[0]


async def call_classifier_model(message: str, recent_context: str, system_prompt: str) -> ClassificationResult:
    full_message = message
    if recent_context:
        full_message = f"[Previous AI message for context: {recent_context}]\n\nUser message to classify: {message}"

    response = await _client.chat.completions.create(
        model=FIREWORKS_MODEL_CLASSIFIER,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": full_message}],
        temperature=0.0,
        max_tokens=256,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
        return ClassificationResult(**data)
    except Exception:
        return ClassificationResult(
            regime="exploratory",
            confidence="llm_low",
            needs_disambiguation=False,
            reasoning="Classifier returned malformed output; defaulted to exploratory."
        )


async def call_structured_output(
    messages: list[dict[str, Any]],
    system_prompt: str,
    schema_class,
    temperature: float = 0.1,
) -> Any:
    schema_hint = (
        f"\n\nRespond with a single JSON object with exactly these fields "
        f"(no extra fields, no nesting):\n{json.dumps(schema_class.model_json_schema()['properties'])}"
    )
    response = await _client.chat.completions.create(
        model=FIREWORKS_MODEL_MAIN,
        messages=[{"role": "system", "content": system_prompt + schema_hint}, *messages],
        temperature=temperature,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Structured output failed to parse as {schema_class.__name__}: {e}. Raw: {raw[:500]}")
