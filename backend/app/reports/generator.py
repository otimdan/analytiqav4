import asyncio
from datetime import datetime
from typing import Any
from app.db.artifacts import get_artifacts_for_session
from app.db.sessions import get_session
from app.db.aio import run_db
from app.db.models import Artifact

_STAGE_ORDER = ["data_preparation", "descriptive", "inferential", "visualisation", "interpretation"]
_STAGE_LABELS = {"data_preparation": "Data Preparation", "descriptive": "Descriptive Statistics", "inferential": "Inferential Analysis", "visualisation": "Visualisations", "interpretation": "Interpretation"}


async def generate_report(session_id: str) -> dict[str, Any]:
    session = await run_db(get_session, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # Body uses the current (non-superseded) artifacts. The statistical summary
    # additionally pulls the FULL family (including superseded re-runs) so the
    # multiple-comparisons correction sees every test actually performed — a
    # significant result that only survived after several attempts on the same
    # pair should not be reported at face value.
    artifacts = await run_db(get_artifacts_for_session, session_id, include_superseded=False)
    all_artifacts = await run_db(get_artifacts_for_session, session_id, include_superseded=True)
    if not artifacts:
        raise ValueError("No completed analyses found. Run some analyses first before generating a report.")

    by_stage: dict[str, list[Artifact]] = {stage: [] for stage in _STAGE_ORDER}
    for artifact in artifacts:
        if artifact.stage in by_stage:
            by_stage[artifact.stage].append(artifact)

    stages_covered = [s for s in _STAGE_ORDER if by_stage[s]]
    sections: list[str] = []
    sections.append(_build_title(session, stages_covered))

    if session.hypothesis_text:
        sections.append(_build_research_question_section(session))

    for stage in _STAGE_ORDER:
        stage_artifacts = by_stage[stage]
        if not stage_artifacts:
            continue
        # Only emit the stage header if at least one artifact renders something
        # (replay-only 'derived_column' artifacts render nothing).
        rendered = [s for s in (_build_artifact_section(a) for a in stage_artifacts) if s]
        if not rendered:
            continue
        sections.append(f"## {_STAGE_LABELS.get(stage, stage.title())}\n")
        sections.extend(rendered)

    test_results = [a for a in all_artifacts if a.artifact_type == "test_result"]
    if test_results:
        sections.append(_build_summary_section(test_results))

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
    if content.get("coefficients"):
        return _format_regression(content)
    test_name = content.get("display_name", "Statistical Test")
    p_value = content.get("p_value")
    statistic = content.get("statistic")
    interpretation = content.get("interpretation", "")
    reasoning = content.get("reasoning", "")
    assumption_results = content.get("assumption_results", {})

    lines = [f"### {test_name}"]
    if var_str: lines.append(f"**Variables:** {var_str}")
    if not content.get("engine_verified", True):
        lines.append("> ⚠️ Assisted analysis — chosen and written by the assistant, not from the verified test library.")
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
    posthoc = content.get("posthoc")
    if posthoc and posthoc.get("comparisons"):
        lines.append("")
        lines.append(f"**Post-hoc pairwise comparisons ({posthoc.get('method', '')}):**")
        lines.append("")
        lines.append("| Comparison | Adjusted p | Significant? |")
        lines.append("|------------|-----------|--------------|")
        for c in posthoc["comparisons"]:
            lines.append(f"| {c['group_a']} vs {c['group_b']} | {c['p_adj']:.4f} | {'Yes' if c['significant'] else 'No'} |")
    if interpretation: lines.append(f"\n**Interpretation:**\n{interpretation}")
    suspect = content.get("suspect_result", False)
    suspect_reason = content.get("suspect_reason", "")
    if suspect and suspect_reason: lines.append(f"\n> ⚠️ Note: {suspect_reason}")
    return "\n".join(lines)


def _format_regression(content):
    display = content.get("display_name", "Regression")
    outcome = content.get("outcome", "")
    is_logistic = content.get("model_type") == "logistic"
    lines = [f"### {display}", f"**Outcome:** `{outcome}`"]
    if not content.get("engine_verified", True):
        lines.append("> ⚠️ Not from the verified library.")
    n = content.get("n")
    r2 = content.get("r_squared")
    p = content.get("p_value")
    fit = []
    if n is not None: fit.append(f"N = {n}")
    if r2 is not None: fit.append(f"{'Pseudo R²' if is_logistic else 'R²'} = {r2:.3f}")
    if p is not None: fit.append(f"model p = {p:.4f}")
    if fit: lines.append("**Fit:** " + ", ".join(fit))
    lines.append("")
    # Coefficient table
    if is_logistic:
        lines.append("| Predictor | Coef | Odds ratio | p |")
        lines.append("|-----------|------|-----------|---|")
        for c in content["coefficients"]:
            orv = c.get("odds_ratio")
            lines.append(f"| {c['name']} | {c['coef']:.3f} | {orv:.3f} | {c['p_value']:.4f} |" if orv is not None else f"| {c['name']} | {c['coef']:.3f} | — | {c['p_value']:.4f} |")
    else:
        lines.append("| Predictor | Coef | 95% CI | p |")
        lines.append("|-----------|------|--------|---|")
        for c in content["coefficients"]:
            lines.append(f"| {c['name']} | {c['coef']:.3f} | [{c['ci_low']:.3f}, {c['ci_high']:.3f}] | {c['p_value']:.4f} |")
    # Diagnostics
    diag = content.get("diagnostics", {})
    notes = []
    vif = diag.get("vif", {})
    high_vif = [f"{k} ({v:.1f})" for k, v in vif.items() if v and v > 5]
    if high_vif: notes.append(f"High multicollinearity (VIF>5): {', '.join(high_vif)}")
    bp = diag.get("breusch_pagan_p")
    if bp is not None and bp < 0.05: notes.append(f"Heteroscedasticity indicated (Breusch-Pagan p={bp:.3f})")
    rn = diag.get("residual_normality_p")
    if rn is not None and rn < 0.05: notes.append(f"Non-normal residuals (p={rn:.3f})")
    if notes:
        lines.append("")
        lines.append("**Diagnostic flags:** " + "; ".join(notes))
    interp = content.get("interpretation")
    if interp:
        lines.append(f"\n**Interpretation:**\n{interp}")
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


def _bh_adjust(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up FDR adjustment. Returns adjusted p-values in
    the same order as the input."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])  # ascending by p
    adj = [1.0] * m
    min_so_far = 1.0
    # Walk from the largest p (rank m) down to the smallest (rank 1).
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        val = pvals[idx] * m / rank
        min_so_far = min(min_so_far, val)
        adj[idx] = min(min_so_far, 1.0)
    return adj


def _build_summary_section(test_artifacts):
    """Summarise every statistical test performed this session. Verified-library
    tests are corrected for multiple comparisons (Benjamini-Hochberg); assisted,
    unverified analyses are listed separately and NOT pooled into the correction
    (their Type-I error rate isn't characterised the way a verified test's is)."""
    verified = [a for a in test_artifacts if (a.content or {}).get("engine_verified", True)]
    assisted = [a for a in test_artifacts if not (a.content or {}).get("engine_verified", True)]

    lines = ["## Summary of Statistical Results"]

    v_with_p = [a for a in verified if (a.content or {}).get("p_value") is not None]
    if v_with_p:
        pvals = [float(a.content["p_value"]) for a in v_with_p]
        adjusted = _bh_adjust(pvals)
        multiple = len(v_with_p) > 1
        note = (
            f"\n{len(v_with_p)} verified tests were run this session. p-values below are "
            "adjusted for multiple comparisons (Benjamini-Hochberg FDR); a result is only "
            "called significant if its **adjusted** p-value is below 0.05."
            if multiple else ""
        )
        lines.append(note)
        header = "| Test | Variables | p-value | Adjusted p | Significant? |"
        lines.append("")
        lines.append(header)
        lines.append("|------|-----------|---------|-----------|--------------|")
        for artifact, adj in zip(v_with_p, adjusted):
            content = artifact.content or {}
            test = content.get("display_name", "Test")
            var_str = " vs ".join(artifact.variables_involved or [])
            p = float(content["p_value"])
            sig = "Yes" if adj < 0.05 else "No"
            adj_str = f"{adj:.4f}" if multiple else "—"
            lines.append(f"| {test} | {var_str} | {p:.4f} | {adj_str} | {sig} |")

    # Verified tests with no parseable p-value.
    for artifact in [a for a in verified if a not in v_with_p]:
        content = artifact.content or {}
        var_str = " vs ".join(artifact.variables_involved or [])
        lines.append(f"| {content.get('display_name', 'Test')} | {var_str} | — | — | — |")

    if assisted:
        lines.append("")
        lines.append("### Assisted analyses (not from the verified test library)")
        lines.append("")
        lines.append("These were chosen and written by the assistant for cases the verified library doesn't cover. Treat them with more caution; they are **not** included in the correction above.")
        lines.append("")
        lines.append("| Analysis | Variables | p-value |")
        lines.append("|----------|-----------|---------|")
        for artifact in assisted:
            content = artifact.content or {}
            var_str = " vs ".join(artifact.variables_involved or [])
            p = content.get("p_value")
            p_str = f"{p:.4f}" if p is not None else "—"
            lines.append(f"| {content.get('display_name', 'Assisted analysis')} | {var_str} | {p_str} |")

    return "\n".join(lines)


def check_report_readiness(session_id: str) -> bool:
    artifacts = get_artifacts_for_session(session_id, include_superseded=False)
    return any(a.stage == "inferential" for a in artifacts)
