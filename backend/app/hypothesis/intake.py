import re
from typing import Any
from app.llm.fireworks_client import call_structured_output
from app.llm.schemas import HypothesisExtraction

_EXTRACTION_SYSTEM_PROMPT = """
You are extracting a research hypothesis or question from text.

Your job is to identify:
1. Whether the text contains a testable research question or hypothesis
2. What the research question is, stated clearly
3. Which variables or concepts are named
4. What type of relationship is implied (difference, association, prediction, or unknown)

Return JSON only matching this schema exactly:
{
  "is_hypothesis": boolean,
  "research_question": string or null,
  "named_variables": [list of variable names or concepts mentioned],
  "matched_columns": [],
  "unmatched_variables": [],
  "hypothesis_type": "difference" | "association" | "prediction" | "unknown" | null
}

is_hypothesis should be false if the text is just exploring, a greeting, or says "just exploring" / "not sure yet".
is_hypothesis should be true if the text states something to be tested or asks whether X affects Y.
"""


async def extract_hypothesis(message: str) -> HypothesisExtraction:
    return await call_structured_output(
        messages=[{"role": "user", "content": message}],
        system_prompt=_EXTRACTION_SYSTEM_PROMPT,
        schema_class=HypothesisExtraction,
        temperature=0.0,
    )


def match_variables_to_columns(named_variables: list[str], available_columns: list[str]) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    unmatched: list[str] = []
    cols_lower = {col.lower().replace("_", " "): col for col in available_columns}

    for var in named_variables:
        var_lower = var.lower().strip()
        found = False

        if var_lower in cols_lower:
            matched.append(cols_lower[var_lower])
            found = True
            continue

        for col_normalized, col_original in cols_lower.items():
            if var_lower in col_normalized:
                matched.append(col_original)
                found = True
                break

        if found:
            continue

        var_words = set(var_lower.split())
        for col_normalized, col_original in cols_lower.items():
            col_words = set(col_normalized.split())
            overlap = var_words & col_words
            if len(overlap) >= max(1, len(var_words) // 2):
                matched.append(col_original)
                found = True
                break

        if not found:
            unmatched.append(var)

    return matched, unmatched


def suggest_near_matches(unmatched_variable: str, available_columns: list[str]) -> list[str]:
    var_lower = unmatched_variable.lower().strip()
    var_words = set(var_lower.split())
    scored: list[tuple[float, str]] = []
    for col in available_columns:
        col_normalized = col.lower().replace("_", " ")
        col_words = set(col_normalized.split())
        overlap = len(var_words & col_words)
        substring_bonus = 1 if var_lower in col_normalized else 0
        score = overlap + substring_bonus
        if score > 0:
            scored.append((score, col))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [col for _, col in scored[:3]]


def store_hypothesis(hypothesis_text: str, matched_columns: list[str]) -> dict[str, Any]:
    return {
        "hypothesis_text": hypothesis_text,
        "hypothesis_columns": matched_columns,
        "hypothesis_on_record": True,
        "suggestion_mode": True,
    }
