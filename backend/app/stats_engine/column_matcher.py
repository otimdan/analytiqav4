"""Work out which columns a plain-English question is about.

The previous rule was `col.lower() in message.lower()`. Column names carry
underscores and users do not, so every natural phrasing missed:

    "Does exam score differ across stress levels?"  ->  []   (exam_score, stress_level)
    "study hours and exam score"                    ->  []   (study_hours_per_week, exam_score)

Confirmatory then had nothing to test and replied "I need two columns to run a
test" to questions that named both. It also poisoned the follow-up path: charts
were logged with no `variables_involved`, so `focus_variables` was empty and
"is that significant?" had no context to fall back on either.

Matching is on token sequences rather than substrings, so "age" does not match
inside "average", and a prefix ("study hours") only counts when it identifies
exactly one column.
"""

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Values too generic to imply a column on their own. "male"/"female" are
# deliberately NOT here: they are exactly how people name a gender column
# without naming it ("between male and female students").
_VALUE_STOPWORDS = {
    "yes", "no", "true", "false", "none", "other", "nan", "na", "nr", "n", "y",
}


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _singular(token: str) -> str:
    """Strip a plural 's' without damaging stems that legitimately end in one.

    "scores" -> "score" and "levels" -> "level", while "stress" and "status"
    survive intact — both are real column stems here.
    """
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _normalise(text: str) -> list[str]:
    return [_singular(t) for t in _tokens(text)]


def _is_identifier(col_tokens: list[str]) -> bool:
    return col_tokens[-1] in {"id", "identifier", "code", "key"}


def _contains_span(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


def match_columns(message: str, columns: list[str], profile: dict[str, Any] | None = None) -> list[str]:
    """Columns the message refers to, most confident first.

    Exact token-sequence matches rank above prefix matches, which rank above
    columns inferred from their category values.
    """
    msg = _normalise(message)
    if not msg:
        return []

    exact: list[str] = []
    prefix_hits: dict[str, list[str]] = {}

    for col in columns:
        col_tokens = _normalise(col)
        if not col_tokens:
            continue
        if _contains_span(msg, col_tokens):
            exact.append(col)
            continue
        # Identifier columns are never the subject of an analysis, and their
        # stem is usually a plain noun in the sentence — "students" matched
        # student_id and beat the gender column it should have found.
        if _is_identifier(col_tokens):
            continue
        # "study hours" for study_hours_per_week. Recorded per prefix so an
        # ambiguous one (two columns starting the same way) can be discarded.
        for size in range(len(col_tokens) - 1, 0, -1):
            candidate = col_tokens[:size]
            if _contains_span(msg, candidate):
                prefix_hits.setdefault(" ".join(candidate), []).append(col)
                break

    resolved = list(exact)
    for _, cols in prefix_hits.items():
        if len(cols) == 1 and cols[0] not in resolved:
            resolved.append(cols[0])

    if profile:
        for col in _columns_from_values(msg, columns, profile):
            if col not in resolved:
                resolved.append(col)

    return resolved


def _columns_from_values(msg: list[str], columns: list[str], profile: dict[str, Any]) -> list[str]:
    """Infer a column the user named only by its values.

    "Do exam scores differ between male and female students?" names gender only
    through its categories. Two distinct values must appear before this fires —
    one is too weak a signal and would misfire on ordinary prose.
    """
    found: list[str] = []
    col_profiles = profile.get("columns", {})
    for col in columns:
        values = col_profiles.get(col, {}).get("top_values") or {}
        seen = set()
        for value in values:
            tokens = _normalise(str(value))
            if len(tokens) != 1 or tokens[0] in _VALUE_STOPWORDS or len(tokens[0]) < 3:
                continue
            if _contains_span(msg, tokens):
                seen.add(tokens[0])
        if len(seen) >= 2:
            found.append(col)
    return found
