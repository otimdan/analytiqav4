import re
from typing import Any

_THINKING_LEAK_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[thinking\].*?\[/thinking\]", re.DOTALL | re.IGNORECASE),
    re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"<thinking>.*$", re.DOTALL | re.IGNORECASE),
]

_REGIME_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "advisory": {"forbidden_empty": True, "required_fields": [], "may_have_images": False},
    "pedagogy": {"forbidden_empty": True, "required_fields": [], "may_have_images": False},
    "exploratory": {"forbidden_empty": False, "required_fields": [], "may_have_images": True},
    "confirmatory": {"forbidden_empty": True, "required_fields": ["test_name", "p_value"], "may_have_images": False},
    "orientation": {"forbidden_empty": True, "required_fields": [], "may_have_images": False},
    "meta": {"forbidden_empty": False, "required_fields": [], "may_have_images": False},
}


class ValidationResult:
    def __init__(self, passed: bool, cleaned_text: str, failure_reason: str | None = None, had_thinking_leak: bool = False):
        self.passed = passed
        self.cleaned_text = cleaned_text
        self.failure_reason = failure_reason
        self.had_thinking_leak = had_thinking_leak


def validate_output(regime: str, response_text: str, artifact_content: dict[str, Any] | None = None, has_images: bool = False) -> ValidationResult:
    requirements = _REGIME_REQUIREMENTS.get(regime, _REGIME_REQUIREMENTS["exploratory"])
    cleaned, had_leak = _strip_thinking_leaks(response_text)
    is_effectively_empty = not cleaned.strip() and not has_images and not artifact_content

    if requirements["forbidden_empty"] and is_effectively_empty:
        return ValidationResult(False, "", f"Regime '{regime}' produced empty output with no images or artifacts.", had_leak)

    required_fields = requirements.get("required_fields", [])
    if required_fields and artifact_content:
        missing = [f for f in required_fields if f not in artifact_content]
        if missing:
            return ValidationResult(False, cleaned, f"Confirmatory output missing required fields: {', '.join(missing)}", had_leak)

    return ValidationResult(True, cleaned, had_thinking_leak=had_leak)


def _strip_thinking_leaks(text: str) -> tuple[str, bool]:
    had_leak = False
    cleaned = text
    for pattern in _THINKING_LEAK_PATTERNS:
        if pattern.search(cleaned):
            had_leak = True
            cleaned = pattern.sub("", cleaned).strip()
    return cleaned, had_leak


def get_fallback_message(regime: str, failure_reason: str) -> str:
    fallbacks = {
        "confirmatory": "I ran the analysis but the result didn't come back in the expected format. Want me to try again?",
        "exploratory": "Something went wrong generating that output. Want me to try a different approach?",
        "advisory": "I wasn't able to answer that from the dataset information. Could you rephrase?",
    }
    return fallbacks.get(regime, "Something went wrong. Want me to try again?")
