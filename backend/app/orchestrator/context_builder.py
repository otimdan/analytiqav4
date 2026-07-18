from typing import Any
from app.config import TOKEN_LIMIT
from app.db.models import Session, Message, Artifact
from app.db.artifacts import get_artifacts_for_session
from app.profiling.cache import get_cached_profile

RECENT_TURNS_TO_KEEP = 6
CHARS_PER_TOKEN = 3


def build_context(session: Session, recent_messages: list[Message]) -> dict[str, Any]:
    profile = get_cached_profile(str(session.id))
    profile_summary = _build_profile_summary(profile, session.dataset_filename or "dataset")
    hypothesis_context = _build_hypothesis_context(session)
    artifacts = get_artifacts_for_session(str(session.id), include_superseded=False)
    artifact_summary = _build_artifact_summary(artifacts)
    focus_variables = _most_recent_variables(artifacts)
    trimmed_turns = _trim_recent_turns(recent_messages)
    return {
        "profile_summary": profile_summary,
        "hypothesis_context": hypothesis_context,
        "artifact_summary": artifact_summary,
        # The variables the user was last working with (last chart/test). Lets a
        # follow-up like "is that significant?" reuse them instead of re-asking.
        "focus_variables": focus_variables,
        "recent_turns": trimmed_turns,
        # Explicit task mode drives handler behavior (directive vs soft nudges,
        # the guided assumption-check pause) — replaces the old inferred booleans.
        "mode": getattr(session, "mode", "explore"),
        "dataset_filename": session.dataset_filename or "dataset",
    }


def _most_recent_variables(artifacts: list[Artifact]) -> list[str]:
    for artifact in reversed(artifacts):
        if artifact.variables_involved and len(artifact.variables_involved) >= 2:
            return list(artifact.variables_involved)
    return []


def _build_profile_summary(profile: dict[str, Any] | None, dataset_filename: str) -> str:
    if not profile or not profile.get("columns"):
        return "No dataset profile available."

    row_count = profile.get("row_count", "unknown")
    columns = profile.get("columns", {})
    lines = [f"'{dataset_filename}': {row_count} rows, {len(columns)} columns."]
    for name, col in columns.items():
        semantic = col.get("semantic_guess", "unknown")
        null_pct = col.get("null_pct", 0)
        detail = f"  - {name} ({semantic}, {col.get('pandas_dtype', '?')}, {null_pct}% missing"
        if semantic in ("numeric_measurement", "ordinal_scale") and col.get("mean") is not None:
            detail += f", mean={col['mean']}, std={col.get('std')}"
        elif col.get("unique_count") is not None:
            detail += f", {col['unique_count']} unique values"
        detail += ")"
        lines.append(detail)
    return "\n".join(lines)


def _build_hypothesis_context(session: Session) -> str:
    # Keyed off the captured question text (mode drives the rail now, not the old
    # hypothesis_on_record flag).
    if not session.hypothesis_text:
        return ""
    lines = [f"Research question: {session.hypothesis_text}"]
    if session.hypothesis_columns:
        cols = ", ".join(session.hypothesis_columns)
        lines.append(f"Key variables: {cols}")
    return "\n".join(lines)


def _build_artifact_summary(artifacts: list[Artifact]) -> str:
    if not artifacts:
        return ""
    lines = ["Completed analyses this session:"]
    for artifact in artifacts:
        line = _summarise_artifact(artifact)
        if line:
            lines.append(f"  - {line}")
    return "\n".join(lines)


def _summarise_artifact(artifact: Artifact) -> str:
    stage = artifact.stage.replace("_", " ").title()
    atype = artifact.artifact_type
    variables = artifact.variables_involved or []
    var_str = " vs ".join(variables) if variables else ""
    content = artifact.content or {}
    if atype == "test_result":
        test = content.get("display_name") or content.get("test_name", "test")
        p = content.get("p_value")
        p_str = f", p={p:.3f}" if p is not None else ""
        # Hedge assisted-tier results so a later LLM turn doesn't cite them with
        # the same confidence as a verified test.
        tier = "" if content.get("engine_verified", True) else " (LLM-assisted, unverified)"
        return f"{stage}: {test} on {var_str}{p_str}{tier}"
    if atype == "assumption_check":
        rec = content.get("display_name") or content.get("recommended_test", "a test")
        return f"{stage}: assumption checks for {var_str} → {rec}"
    if atype == "chart":
        chart_type = content.get("chart_type", "chart")
        return f"{stage}: {chart_type} of {var_str}"
    if atype == "table":
        return f"{stage}: summary table for {var_str}"
    if atype == "cleaned_dataset":
        ops = content.get("operations_applied", [])
        ops_str = ", ".join(ops) if ops else "cleaning applied"
        return f"{stage}: {ops_str}"
    return f"{stage}: {atype}"


def _trim_recent_turns(messages: list[Message]) -> list[dict[str, str]]:
    recent = messages[-RECENT_TURNS_TO_KEEP:]
    turn_dicts = [{"role": m.role, "content": m.content} for m in recent]
    max_chars = (TOKEN_LIMIT // 2) * CHARS_PER_TOKEN
    while turn_dicts:
        total_chars = sum(len(t["content"]) for t in turn_dicts)
        if total_chars <= max_chars:
            break
        turn_dicts.pop(0)
    return turn_dicts


def format_context_for_prompt(context: dict[str, Any]) -> str:
    parts = []
    if context["profile_summary"]:
        parts.append(f"DATASET:\n{context['profile_summary']}")
    if context["hypothesis_context"]:
        parts.append(f"RESEARCH CONTEXT:\n{context['hypothesis_context']}")
    if context["artifact_summary"]:
        parts.append(context["artifact_summary"])
    return "\n\n".join(parts) if parts else ""
