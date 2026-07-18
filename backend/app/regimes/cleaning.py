"""Data-cleaning regime (Goal 2, Phase B).

The LLM maps the request to ONE operation + params from the fixed menu; the engine
validates and runs the audited transform, then PERSISTS the cleaned dataset
(dataset_csv) and re-profiles it so every later step uses the clean data. Produces
a cleaned_dataset audit artifact. Never LLM-written cleaning code.
"""
import json
import asyncio
from typing import Any

from app.db.models import Session
from app.llm.fireworks_client import call_structured_output
from app.llm.schemas import CleaningSpec
from app.llm.prompts import CLEANING_EXTRACTION_SYSTEM_PROMPT
from app.cleaning.operations import resolve_operation, render_operation, OPERATIONS
from app.sandbox.manager import get_or_create_sandbox
from app.sandbox.executor import execute_code
from app.profiling.profiler import build_profile
from app.profiling.cache import get_cached_profile, set_cached_profile
from app.db.sessions import update_dataset_csv
from app.db.aio import run_db
from app.logging_config import logger


async def handle(message: str, session: Session, context: dict[str, Any]) -> dict[str, Any]:
    profile = await run_db(get_cached_profile, str(session.id))
    if not profile:
        return _text("I need your dataset profile first — try again in a moment.")
    columns = list(profile.get("columns", {}).keys())

    spec = await _extract(message, columns)
    if not spec.is_cleaning or not spec.operation:
        return _text(
            "Tell me what to clean — e.g. \"convert price to numeric\", \"drop rows with "
            "missing values\", \"remove outliers in age\", or \"recode region\"."
        )

    params = _params_from_spec(spec)
    resolved = resolve_operation(spec.operation, params, profile)
    if not resolved.get("ok"):
        return _text(resolved.get("reason", "I couldn't set up that cleaning step."))

    code = render_operation(spec.operation, params)
    sbx = await get_or_create_sandbox(str(session.id))
    exec_result = await execute_code(sbx, code)
    summary = _parse_summary(exec_result.get("stdout", ""))
    if summary is None:
        detail = _first_err(exec_result.get("stderr", ""))
        return _text(f"That cleaning step didn't complete{(' (' + detail + ')') if detail else ''}. Try a different column or rephrase.")

    # Persist the cleaned dataset + re-profile so later analyses use clean data.
    try:
        cleaned_csv = await asyncio.to_thread(sbx.files.read, "/home/user/data.csv")
        await run_db(update_dataset_csv, str(session.id), cleaned_csv)
        new_profile = await build_profile(sbx, str(session.id))
        await run_db(set_cached_profile, str(session.id), new_profile)
    except Exception as e:
        logger.warning("Cleaning persist/re-profile failed: %s", e)

    return {
        "text": _summary_text(spec.operation, params, summary),
        "images": [], "artifact_content": {
            "operation": spec.operation, "params": params, "summary": summary,
            "operations_applied": [_op_detail(spec.operation, params)],
            "rows_affected": _rows_affected(summary),
        },
        "artifact_type": "cleaned_dataset", "stage": "data_preparation",
        "variables_involved": _op_columns(params), "code_used": code,
        "executions": [{"code": code, "output": (exec_result.get("stdout", "") or "").rstrip() or "(no output)"}],
        "suggested_next": None, "next_action": None, "nudge_style": "soft",
        "is_hypothesis_candidate": False, "metered": False,
    }


async def _extract(message: str, columns: list[str]) -> CleaningSpec:
    return await call_structured_output(
        messages=[{"role": "user", "content": f"Columns: {', '.join(columns)}\n\nRequest: {message}"}],
        system_prompt=CLEANING_EXTRACTION_SYSTEM_PROMPT, schema_class=CleaningSpec, temperature=0.0,
    )


def _params_from_spec(spec: CleaningSpec) -> dict[str, Any]:
    d = spec.model_dump(exclude={"is_cleaning", "operation"})
    return {k: v for k, v in d.items() if v is not None}


def _parse_summary(stdout: str):
    for line in reversed((stdout or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                d = json.loads(line)
                if "rows_after" in d or "operation" in d:
                    return d
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _rows_affected(summary: dict[str, Any]) -> int:
    for k in ("removed", "affected", "filled"):
        if k in summary and summary[k] is not None:
            return int(summary[k])
    return abs(int(summary.get("rows_before", 0)) - int(summary.get("rows_after", 0)))


def _op_columns(params: dict[str, Any]) -> list[str]:
    cols = []
    for k in ("column", "left", "old", "new"):
        if params.get(k):
            cols.append(params[k])
    if params.get("columns"):
        cols += list(params["columns"])
    return list(dict.fromkeys(cols))


def _op_detail(op: str, params: dict[str, Any]) -> str:
    label = OPERATIONS.get(op, {}).get("label", op)
    target = params.get("column") or (", ".join(params["columns"]) if params.get("columns") else "") or params.get("old") or ""
    return f"{label}{(' — ' + target) if target else ''}"


def _summary_text(op: str, params: dict[str, Any], s: dict[str, Any]) -> str:
    ra = s.get("rows_after")
    if op == "coerce_numeric":
        return f"Converted **{params['column']}** to numeric. {s.get('new_missing', 0)} value(s) couldn't be parsed and are now missing."
    if op == "impute_missing":
        return f"Filled **{s.get('filled', 0)}** missing value(s) in **{params['column']}** using the {params.get('strategy')}."
    if op == "drop_missing":
        return f"Dropped **{s.get('removed', 0)}** row(s) with missing values — {ra} rows remain."
    if op == "remove_outliers":
        act = "Capped" if params.get("action") == "cap" else "Removed"
        return f"{act} **{s.get('affected', 0)}** outlier(s) in **{params['column']}** ({params.get('method', 'iqr').upper()} method)."
    if op == "recode":
        return f"Recoded **{params['column']}** ({len(params.get('mapping', {}))} value mapping(s))."
    if op == "filter_rows":
        return f"Kept rows where `{params['column']} {params['operator']} {params['value']}` — removed **{s.get('removed', 0)}**, {ra} remain."
    if op == "drop_column":
        return f"Dropped column(s): {', '.join(s.get('dropped', []))}."
    if op == "rename_column":
        return f"Renamed **{params['old']}** to **{params['new']}**."
    if op == "derive_column":
        return f"Created **{params['new']}** = `{params['left']} {params['operator']} {params['right']}`."
    return f"Cleaning applied — {ra} rows."


def _first_err(stderr: str) -> str:
    for line in reversed((stderr or "").strip().split("\n")):
        if line.strip():
            return line.strip()[:140]
    return ""


def _text(msg: str) -> dict[str, Any]:
    return {
        "text": msg, "images": [], "artifact_content": None, "artifact_type": None, "stage": None,
        "variables_involved": None, "code_used": None, "executions": [], "suggested_next": None,
        "next_action": None, "nudge_style": "soft", "is_hypothesis_candidate": False, "metered": False,
    }
