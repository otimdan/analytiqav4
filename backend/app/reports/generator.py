import asyncio
from datetime import datetime
from typing import Any
from app.db.artifacts import get_artifacts_for_session
from app.db.sessions import get_session
from app.db.models import Artifact

_STAGE_ORDER = ["data_preparation", "descriptive", "inferential", "visualisation", "interpretation"]
_STAGE_LABELS = {"data_preparation": "Data Preparation", "descriptive": "Descriptive Statistics", "inferential": "Inferential Analysis", "visualisation": "Visualisations", "interpretation": "Interpretation"}


async def generate_report(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    artifacts = get_artifacts_for_session(session_id, include_superseded=False)
    if not artifacts:
        raise ValueError("No completed analyses found. Run some analyses first before generating a report.")

    by_stage: dict[str, list[Artifact]] = {stage: [] for stage in _STAGE_ORDER}
    for artifact in artifacts:
        if artifact.stage in by_stage:
            by_stage[artifact.stage].append(artifact)

    stages_covered = [s for s in _STAGE_ORDER if by_stage[s]]
    sections: list[str] = []
    sections.append(_build_title(session, stages_covered))

    if session.hypothesis_on_record and session.hypothesis_text:
        sections.append(_build_research_question_section(session))

    for stage in _STAGE_ORDER:
        stage_artifacts = by_stage[stage]
        if not stage_artifacts:
            continue
        label = _STAGE_LABELS.get(stage, stage.title())
        sections.append(f"## {label}\n")
        for artifact in stage_artifacts:
            section = _build_artifact_section(artifact)
            if section:
                sections.append(section)

    inferential = by_stage.get("inferential", [])
    if inferential:
        sections.append(_build_summary_section(inferential))

    markdown = "\n\n".join(sections)
    date_str = datetime.now().strftime("%Y%m%d")
    filename_base = session.dataset_filename.replace(".csv", "") if session.dataset_filename else "analysis"
    filename = f"{filename_base}_report_{date_str}.md"

    return {"markdown": markdown, "filename": filename, "artifact_count": len(artifacts), "stages_covered": stages_covered}


def _build_title(session, stages_covered):
    date_str = datetime.now().strftime("%B %d, %Y")
    dataset = session.dataset_filename or "Dataset"
    return f"# Analysis Report\n\n**Dataset:** {dataset}\n**Generated:** {date_str}\n**Sections:** {', '.join(_STAGE_LABELS[s] for s in stages_covered)}"


def _build_research_question_section(session):
    lines = ["## Research Question", "", session.hypothesis_text]
    if session.hypothesis_columns:
        cols = ", ".join(f"`{c}`" for c in session.hypothesis_columns)
        lines.append(f"\n**Key variables:** {cols}")
    return "\n".join(lines)


def _build_artifact_section(artifact: Artifact) -> str:
    atype = artifact.artifact_type
    content = artifact.content or {}
    variables = artifact.variables_involved or []
    var_str = " and ".join(f"`{v}`" for v in variables)
    if atype == "test_result": return _format_test_result(content, var_str)
    if atype == "chart": return f"### {content.get('chart_type', 'Chart').title()}\n**Variables:** {var_str}\n\n*[Chart: {content.get('chart_type', 'Chart')} of {var_str}]*\n"
    if atype == "table": return _format_table(content, var_str)
    if atype == "cleaned_dataset": return _format_cleaning(content)
    if atype == "summary": return f"{content.get('text_preview', '')}\n"
    return ""


def _format_test_result(content, var_str):
    test_name = content.get("display_name", "Statistical Test")
    p_value = content.get("p_value")
    statistic = content.get("statistic")
    interpretation = content.get("interpretation", "")
    reasoning = content.get("reasoning", "")
    assumption_results = content.get("assumption_results", {})

    lines = [f"### {test_name}"]
    if var_str: lines.append(f"**Variables:** {var_str}")
    if reasoning: lines.append(f"**Why this test:** {reasoning}")
    lines.append("")
    lines.append("**Results:**")
    if statistic is not None: lines.append(f"- Test statistic: {statistic:.4f}")
    if p_value is not None:
        sig = "significant" if p_value < 0.05 else "not significant"
        lines.append(f"- p-value: {p_value:.4f} ({sig} at α=0.05)")
    if assumption_results:
        lines.append("")
        lines.append("**Assumption checks:**")
        for check, result in assumption_results.items():
            if result != "not_applicable":
                lines.append(f"- {check.replace('_', ' ').title()}: {result}")
    if interpretation: lines.append(f"\n**Interpretation:**\n{interpretation}")
    suspect = content.get("suspect_result", False)
    suspect_reason = content.get("suspect_reason", "")
    if suspect and suspect_reason: lines.append(f"\n> ⚠️ Note: {suspect_reason}")
    return "\n".join(lines)


def _format_table(content, var_str):
    columns = content.get("columns", [])
    rows = content.get("rows", [])
    if not columns or not rows:
        return f"### Summary Table\n*No data available.*\n"
    lines = [f"### Summary Table"]
    if var_str: lines.append(f"**Variables:** {var_str}")
    lines.append("")
    lines.append("| " + " | ".join(str(c) for c in columns) + " |")
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in rows[:20]:
        if isinstance(row, (list, tuple)):
            lines.append("| " + " | ".join(str(v) for v in row) + " |")
        elif isinstance(row, dict):
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    if len(rows) > 20: lines.append(f"*({len(rows) - 20} more rows not shown)*")
    return "\n".join(lines)


def _format_cleaning(content):
    ops = content.get("operations_applied", [])
    rows_affected = content.get("rows_affected")
    lines = ["### Data Preparation"]
    if ops:
        lines.append("**Operations applied:**")
        for op in ops: lines.append(f"- {op}")
    if rows_affected is not None: lines.append(f"**Rows affected:** {rows_affected}")
    return "\n".join(lines)


def _build_summary_section(inferential_artifacts):
    lines = ["## Summary of Statistical Results", "", "| Test | Variables | p-value | Significant? |", "|------|-----------|---------|--------------|"]
    for artifact in inferential_artifacts:
        content = artifact.content or {}
        test = content.get("display_name", "Test")
        variables = artifact.variables_involved or []
        var_str = " vs ".join(variables)
        p = content.get("p_value")
        if p is not None:
            sig = "Yes" if p < 0.05 else "No"
            p_str = f"{p:.4f}"
        else:
            sig = "—"
            p_str = "—"
        lines.append(f"| {test} | {var_str} | {p_str} | {sig} |")
    return "\n".join(lines)


def check_report_readiness(session_id: str) -> bool:
    artifacts = get_artifacts_for_session(session_id, include_superseded=False)
    return any(a.stage == "inferential" for a in artifacts)
