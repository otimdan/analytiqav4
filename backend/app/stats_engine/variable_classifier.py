from typing import Any
from app.profiling.profiler import get_column_profile

NUMERIC = "numeric"
NUMERIC_OR_ORDINAL = "numeric_or_ordinal"
CATEGORICAL = "categorical"
ORDINAL = "ordinal"
DATETIME = "datetime"
IDENTIFIER = "identifier"
FREE_TEXT = "free_text"
UNKNOWN = "unknown"


def classify_variable(column_name: str, profile: dict[str, Any]) -> str:
    col = get_column_profile(profile, column_name)
    if not col:
        return UNKNOWN

    semantic = col.get("semantic_guess", "unknown")
    dtype = col.get("pandas_dtype", "")
    uniqueness = col.get("uniqueness_ratio", 0)
    likely_categorical = col.get("likely_categorical", False)
    likely_datetime = col.get("likely_datetime", False)
    is_float = "float" in dtype
    is_int = "int" in dtype
    is_numeric = is_float or is_int
    # Object OR the newer pandas string dtype ('str'/'string') OR category.
    is_stringy = ("object" in dtype) or ("str" in dtype) or ("categor" in dtype)

    # 1. Datetime only when the values ACTUALLY parse as dates — never from a
    #    name guess alone (a text "session_time" of 'morning'/'evening' is
    #    categorical, not datetime).
    if likely_datetime:
        return DATETIME

    # 2. Continuous float measurements are numeric, full stop. High uniqueness is
    #    the norm for continuous data, so it must never mark a float as an id.
    if is_float:
        return NUMERIC_OR_ORDINAL if semantic == "ordinal_scale" else NUMERIC

    # 3. An ordinal-scale NAME on an integer (a Likert score/grade/rating) keeps
    #    its ordering for rank-based tests, even if few-valued — beats the
    #    categorical heuristics. (Only for numeric ints: a *text* 'grade' of
    #    'low/mid/high' can't be used ordinally without encoding, so it's
    #    categorical and handled below.)
    if is_int and semantic == "ordinal_scale":
        return NUMERIC_OR_ORDINAL

    # 4. Identifiers: an explicit name-based guess, or an all-unique NON-numeric
    #    column (unique strings = names/emails/codes). A high-uniqueness numeric
    #    column is continuous data, not an id, unless its name said so.
    if semantic == "identifier":
        return IDENTIFIER
    if uniqueness > 0.95 and not is_numeric:
        return IDENTIFIER
    if semantic == "free_text":
        return FREE_TEXT

    # 5. Categorical: profiler-flagged few-valued ints, string/object columns,
    #    or a categorical-grouping name.
    if likely_categorical or is_stringy or semantic == "categorical_grouping":
        return CATEGORICAL

    # 6. Any remaining numeric.
    if is_numeric:
        return NUMERIC

    return UNKNOWN


def classify_pair(var_a: str, var_b: str, profile: dict[str, Any]) -> tuple[str, str]:
    type_a = classify_variable(var_a, profile)
    type_b = classify_variable(var_b, profile)
    if type_a == CATEGORICAL and type_b in [NUMERIC, NUMERIC_OR_ORDINAL]:
        return type_b, type_a
    return type_a, type_b


def get_group_count(grouping_column: str, profile: dict[str, Any]) -> int:
    col = get_column_profile(profile, grouping_column)
    if not col:
        return 0
    return col.get("group_count") or col.get("unique_count", 0)


def is_suitable_for_analysis(column_name: str, profile: dict[str, Any]) -> tuple[bool, str]:
    col = get_column_profile(profile, column_name)
    if not col:
        return False, f"Column '{column_name}' not found in dataset."

    var_type = classify_variable(column_name, profile)

    if var_type == IDENTIFIER:
        return False, f"'{column_name}' looks like an ID column. ID columns aren't suitable for statistical analysis."
    if var_type == FREE_TEXT:
        return False, f"'{column_name}' contains free text and can't be used in a statistical test directly."
    if var_type == UNKNOWN:
        return False, f"'{column_name}' couldn't be classified. Check that the column contains consistent values."

    null_pct = col.get("null_pct", 0)
    if null_pct > 80:
        return False, f"'{column_name}' is {null_pct}% missing. A column with this much missing data will produce unreliable results."

    return True, ""
