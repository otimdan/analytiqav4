"""Deterministic data-cleaning operations (Goal 2).

Same philosophy as the stats engine: the LLM picks an operation + parameters from
a FIXED menu; the engine validates them and runs an AUDITED template. No arbitrary
LLM-written cleaning code. Each operation rewrites the working CSV in place and
prints a JSON summary (rows before/after, what changed) for the audit log.

Column names and values are injected only as repr()'d literals — injection-safe.
"""
import json
from typing import Any, Optional

from app.profiling.profiler import get_column_profile

# op -> (required params, optional params, human label)
OPERATIONS: dict[str, dict[str, Any]] = {
    "drop_missing":    {"required": [], "optional": ["columns"], "label": "Drop rows with missing values"},
    "impute_missing":  {"required": ["column", "strategy"], "optional": ["value"], "label": "Fill missing values"},
    "coerce_numeric":  {"required": ["column"], "optional": [], "label": "Convert a column to numeric"},
    "remove_outliers": {"required": ["column"], "optional": ["method", "action"], "label": "Handle outliers"},
    "recode":          {"required": ["column", "mapping"], "optional": [], "label": "Recode / merge categories"},
    "filter_rows":     {"required": ["column", "operator", "value"], "optional": [], "label": "Filter rows"},
    "drop_column":     {"required": ["columns"], "optional": [], "label": "Drop columns"},
    "rename_column":   {"required": ["old", "new"], "optional": [], "label": "Rename a column"},
    "derive_column":   {"required": ["new", "left", "operator", "right", "right_is_col"], "optional": [], "label": "Create a derived column"},
}

_STRATEGIES = {"mean", "median", "mode", "constant"}
_OUTLIER_METHODS = {"iqr", "zscore"}
_OUTLIER_ACTIONS = {"remove", "cap"}
_FILTER_OPS = {"==", "!=", ">", "<", ">=", "<="}
_DERIVE_OPS = {"+", "-", "*", "/"}


def resolve_operation(op: str, params: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Validate an operation + params against the dataset. Returns {ok: True,...}
    or {ok: False, reason}."""
    spec = OPERATIONS.get(op)
    if not spec:
        return _err(f"Unknown cleaning operation '{op}'.")
    for p in spec["required"]:
        if params.get(p) in (None, "", []):
            return _err(f"'{op}' needs a '{p}'.")

    cols = set((profile or {}).get("columns", {}).keys())

    def col_ok(name):
        return name in cols

    # column existence checks
    if op in ("impute_missing", "coerce_numeric", "remove_outliers", "recode", "filter_rows"):
        if not col_ok(params["column"]):
            return _err(f"Column '{params['column']}' isn't in the dataset.")
    if op == "drop_column":
        missing = [c for c in params["columns"] if not col_ok(c)]
        if missing:
            return _err(f"Column(s) not found: {', '.join(missing)}.")
    if op == "drop_missing" and params.get("columns"):
        missing = [c for c in params["columns"] if not col_ok(c)]
        if missing:
            return _err(f"Column(s) not found: {', '.join(missing)}.")
    if op == "rename_column" and not col_ok(params["old"]):
        return _err(f"Column '{params['old']}' isn't in the dataset.")

    # value-domain checks
    if op == "impute_missing":
        if params["strategy"] not in _STRATEGIES:
            return _err(f"Imputation strategy must be one of {sorted(_STRATEGIES)}.")
        if params["strategy"] == "constant" and params.get("value") in (None, ""):
            return _err("Constant imputation needs a 'value'.")
    if op == "remove_outliers":
        if params.get("method", "iqr") not in _OUTLIER_METHODS:
            return _err(f"Outlier method must be one of {sorted(_OUTLIER_METHODS)}.")
        if params.get("action", "remove") not in _OUTLIER_ACTIONS:
            return _err(f"Outlier action must be one of {sorted(_OUTLIER_ACTIONS)}.")
    if op == "filter_rows" and params["operator"] not in _FILTER_OPS:
        return _err(f"Filter operator must be one of {sorted(_FILTER_OPS)}.")
    if op == "recode" and not isinstance(params["mapping"], dict):
        return _err("Recode needs a mapping of old value -> new value.")
    if op == "derive_column":
        if params["operator"] not in _DERIVE_OPS:
            return _err(f"Derived-column operator must be one of {sorted(_DERIVE_OPS)}.")
        if not col_ok(params["left"]):
            return _err(f"Column '{params['left']}' isn't in the dataset.")
        if params.get("right_is_col") and not col_ok(params["right"]):
            return _err(f"Column '{params['right']}' isn't in the dataset.")

    return {"ok": True, "operation": op, "params": params}


def _err(reason: str) -> dict[str, Any]:
    return {"ok": False, "reason": reason}


# ── Templates ─────────────────────────────────────────────────────────────────
_HEADER = """
import pandas as pd, numpy as np, json
df = pd.read_csv('/home/user/data.csv')
_before = len(df)
_summary = {}
"""

_FOOTER = """
df.to_csv('/home/user/data.csv', index=False)
_summary["rows_before"] = int(_before)
_summary["rows_after"] = int(len(df))
_summary["columns"] = list(df.columns)
print(json.dumps(_summary, default=str))
"""

_BODIES: dict[str, str] = {
    "drop_missing": """
_subset = __COLUMNS__
df = df.dropna(subset=_subset) if _subset else df.dropna()
_summary = {"operation": "drop_missing", "subset": _subset, "removed": int(_before - len(df))}
""",
    "impute_missing": """
_col, _strategy, _value = __COLUMN__, __STRATEGY__, __VALUE__
_n = int(df[_col].isna().sum())
if _strategy == "mean": _fill = df[_col].mean()
elif _strategy == "median": _fill = df[_col].median()
elif _strategy == "mode": _fill = (df[_col].mode().iloc[0] if not df[_col].mode().empty else None)
else: _fill = _value
df[_col] = df[_col].fillna(_fill)
_summary = {"operation": "impute_missing", "column": _col, "strategy": _strategy, "filled": _n, "fill_value": _fill}
""",
    "coerce_numeric": """
_col = __COLUMN__
_orig_missing = int(df[_col].isna().sum())
df[_col] = pd.to_numeric(df[_col].astype(str).str.replace(r'[^0-9.\\-eE]', '', regex=True).replace('', np.nan), errors='coerce')
_summary = {"operation": "coerce_numeric", "column": _col, "new_missing": int(df[_col].isna().sum()) - _orig_missing}
""",
    "remove_outliers": """
_col, _method, _action = __COLUMN__, __METHOD__, __ACTION__
_s = df[_col]
if _method == "zscore":
    _m, _sd = _s.mean(), _s.std(); _lower, _upper = _m - 3*_sd, _m + 3*_sd
else:
    _q1, _q3 = _s.quantile(0.25), _s.quantile(0.75); _iqr = _q3 - _q1; _lower, _upper = _q1 - 1.5*_iqr, _q3 + 1.5*_iqr
_out = ((_s < _lower) | (_s > _upper))
if _action == "cap":
    df[_col] = _s.clip(_lower, _upper); _affected = int(_out.sum())
else:
    df = df[~_out.fillna(False)]; _affected = int(_out.sum())
_summary = {"operation": "remove_outliers", "column": _col, "method": _method, "action": _action, "affected": _affected, "bounds": [float(_lower), float(_upper)]}
""",
    "recode": """
_col, _mapping = __COLUMN__, __MAPPING__
df[_col] = df[_col].astype(str).replace(_mapping)
_summary = {"operation": "recode", "column": _col, "mapping": _mapping}
""",
    "filter_rows": """
_col, _op, _val = __COLUMN__, __OP__, __VALUE__
_s = df[_col]
if _op == "==": _mask = _s == _val
elif _op == "!=": _mask = _s != _val
elif _op == ">": _mask = pd.to_numeric(_s, errors="coerce") > _val
elif _op == "<": _mask = pd.to_numeric(_s, errors="coerce") < _val
elif _op == ">=": _mask = pd.to_numeric(_s, errors="coerce") >= _val
else: _mask = pd.to_numeric(_s, errors="coerce") <= _val
df = df[_mask.fillna(False)]
_summary = {"operation": "filter_rows", "column": _col, "operator": _op, "value": _val, "removed": int(_before - len(df))}
""",
    "drop_column": """
_cols = __COLUMNS__
_dropped = [c for c in _cols if c in df.columns]
df = df.drop(columns=_dropped)
_summary = {"operation": "drop_column", "dropped": _dropped}
""",
    "rename_column": """
df = df.rename(columns={__OLD__: __NEW__})
_summary = {"operation": "rename_column", "from": __OLD__, "to": __NEW__}
""",
    "derive_column": """
_new, _left, _op, _right, _rcol = __NEW__, __LEFT__, __OP__, __RIGHT__, __RIGHT_IS_COL__
_r = df[_right] if _rcol else _right
if _op == "+": df[_new] = df[_left] + _r
elif _op == "-": df[_new] = df[_left] - _r
elif _op == "*": df[_new] = df[_left] * _r
else: df[_new] = df[_left] / _r
_summary = {"operation": "derive_column", "new_column": _new, "from": _left, "operator": _op}
""",
}

_SENTINEL_PARAM = {
    "__COLUMN__": "column", "__COLUMNS__": "columns", "__STRATEGY__": "strategy",
    "__VALUE__": "value", "__METHOD__": "method", "__ACTION__": "action",
    "__MAPPING__": "mapping", "__OP__": "operator", "__OLD__": "old", "__NEW__": "new",
    "__LEFT__": "left", "__RIGHT__": "right", "__RIGHT_IS_COL__": "right_is_col",
}

_DEFAULTS = {"method": "iqr", "action": "remove", "value": None}


def render_operation(op: str, params: dict[str, Any]) -> Optional[str]:
    """Assemble the injection-safe transform script for an operation. Every
    parameter is inserted as its repr() (safe Python literal)."""
    body = _BODIES.get(op)
    if body is None:
        return None
    filled = body
    for sentinel, key in _SENTINEL_PARAM.items():
        if sentinel in filled:
            val = params.get(key, _DEFAULTS.get(key))
            filled = filled.replace(sentinel, repr(val))
    return _HEADER + filled + _FOOTER
