import asyncio
import json
from typing import Any, Optional
from e2b_code_interpreter import Sandbox

PROFILE_SCRIPT = r"""
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

df = pd.read_csv('/home/user/data.csv')
profile = {"row_count": int(len(df)), "column_count": int(len(df.columns)), "columns": {}}

for col in df.columns:
    series = df[col]
    col_profile = {}
    dtype_str = str(series.dtype)
    col_profile["pandas_dtype"] = dtype_str
    null_count = int(series.isnull().sum())
    col_profile["null_count"] = null_count
    col_profile["null_pct"] = round(null_count / len(df) * 100, 2)
    unique_count = int(series.nunique())
    col_profile["unique_count"] = unique_count
    col_profile["uniqueness_ratio"] = round(unique_count / max(len(df), 1), 4)

    if pd.api.types.is_numeric_dtype(series):
        clean = series.dropna()
        col_profile["mean"] = round(float(clean.mean()), 4) if len(clean) else None
        col_profile["median"] = round(float(clean.median()), 4) if len(clean) else None
        col_profile["std"] = round(float(clean.std()), 4) if len(clean) else None
        col_profile["min"] = round(float(clean.min()), 4) if len(clean) else None
        col_profile["max"] = round(float(clean.max()), 4) if len(clean) else None
        col_profile["q25"] = round(float(clean.quantile(0.25)), 4) if len(clean) else None
        col_profile["q75"] = round(float(clean.quantile(0.75)), 4) if len(clean) else None
        col_profile["skewness"] = round(float(clean.skew()), 4) if len(clean) > 2 else None
        if 'int' in dtype_str and unique_count <= 10:
            col_profile["likely_categorical"] = True
            col_profile["value_counts"] = series.value_counts().head(10).to_dict()
        else:
            col_profile["likely_categorical"] = False
    elif pd.api.types.is_object_dtype(series) or dtype_str == 'category':
        # ^^^ replaced is_categorical_dtype (removed in pandas 2.2)
        col_profile["top_values"] = series.value_counts().head(10).to_dict()
        col_profile["group_count"] = unique_count

    # Datetime detection — removed infer_datetime_format (removed in pandas 2.2)
    if pd.api.types.is_object_dtype(series):
        try:
            parsed = pd.to_datetime(series, errors='coerce')
            col_profile["likely_datetime"] = parsed.notna().sum() > len(df) * 0.8
        except Exception:
            col_profile["likely_datetime"] = False
    else:
        col_profile["likely_datetime"] = pd.api.types.is_datetime64_any_dtype(series)

    name_lower = col.lower()
    is_numeric_col = pd.api.types.is_numeric_dtype(series)
    is_float_col = pd.api.types.is_float_dtype(series)
    # Tight id-name test (word-ish), so 'diagnosis' isn't tagged an id by 'no'.
    id_name = (name_lower in ("id", "index") or name_lower.endswith("_id")
               or name_lower.endswith("id") and len(name_lower) <= 6
               or any(kw in name_lower for kw in ["uuid", "guid", "_code", "_ref", "_key"]))
    if col_profile.get("likely_datetime"):
        # Only when the values actually parse as dates (not a name guess).
        col_profile["semantic_guess"] = "datetime"
    elif not is_numeric_col and col_profile.get("uniqueness_ratio", 0) > 0.95:
        # All-unique NON-numeric column = identifier (names, emails, codes).
        col_profile["semantic_guess"] = "identifier"
    elif id_name and not is_float_col:
        col_profile["semantic_guess"] = "identifier"
    elif any(kw in name_lower for kw in ["group", "arm", "intervention", "treatment",
                                           "village", "region", "district", "sex",
                                           "gender", "category", "type", "status"]):
        col_profile["semantic_guess"] = "categorical_grouping"
    elif any(kw in name_lower for kw in ["score", "severity", "level", "grade",
                                           "stage", "rank", "rating"]):
        col_profile["semantic_guess"] = "ordinal_scale"
    elif any(kw in name_lower for kw in ["age", "weight", "height", "bp", "bmi",
                                           "income", "cost", "price", "count",
                                           "duration", "distance"]):
        col_profile["semantic_guess"] = "numeric_measurement"
    elif any(kw in name_lower for kw in ["name", "comment", "notes", "description",
                                           "address", "reason"]):
        col_profile["semantic_guess"] = "free_text"
    else:
        col_profile["semantic_guess"] = "unknown"

    profile["columns"][col] = col_profile


def _native(o):
    # value_counts().to_dict() and boolean comparisons leak numpy scalar types
    # (np.bool_, np.int64, np.float64) into the profile as both keys and values;
    # the stdlib json encoder can't serialize those. Coerce everything to native
    # Python before dumping.
    if isinstance(o, dict):
        return {_native(k): _native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_native(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return o


print(json.dumps(_native(profile)))
"""


async def build_profile(sbx: Sandbox, session_id: str) -> dict[str, Any]:
    execution = await asyncio.to_thread(sbx.run_code, PROFILE_SCRIPT)
    if execution.error:
        raise RuntimeError(f"Profiling failed for session {session_id}: {execution.error.value}")

    stdout = "".join(execution.logs.stdout) if execution.logs.stdout else ""
    try:
        return json.loads(stdout.strip())
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"Could not parse profiling output for session {session_id}: {e}")


def get_column_profile(profile: dict[str, Any], column_name: str) -> Optional[dict[str, Any]]:
    return (profile or {}).get("columns", {}).get(column_name)
