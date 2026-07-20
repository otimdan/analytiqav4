"""Tool results are re-sent on every later model call, so they must stay bounded.

A real session printed several full `df.to_string()` dumps of an 81-column frame;
by step 6 the conversation was mostly stale tables and the model returned empty
content instead of an answer.
"""

from app.sandbox.executor import build_tool_result_string, _MAX_TOOL_OUTPUT_CHARS


def _result(stdout="", stderr="", images=()):
    return {"stdout": stdout, "stderr": stderr, "images": list(images), "success": not stderr}


def test_short_output_is_passed_through_untouched():
    assert build_tool_result_string(_result(stdout="Shape: (45, 81)")) == "Shape: (45, 81)"


def test_huge_output_is_capped():
    huge = "col_value_" * 20_000  # 200k chars
    out = build_tool_result_string(_result(stdout=huge))
    assert len(out) < _MAX_TOOL_OUTPUT_CHARS * 2
    assert "truncated" in out


def test_truncation_keeps_both_ends():
    """The head carries the schema, the tail carries the computed result —
    dropping either leaves the model unable to write the answer."""
    body = "\n".join(f"row {i}" for i in range(20_000))
    stdout = f"HEAD_MARKER\n{body}\nTAIL_MARKER"
    out = build_tool_result_string(_result(stdout=stdout))
    assert "HEAD_MARKER" in out
    assert "TAIL_MARKER" in out


def test_chart_and_error_markers_survive_truncation():
    out = build_tool_result_string(_result(stdout="x" * 50_000, stderr="boom", images=["b64"]))
    assert "[execution produced an error]" in out
    assert "[1 chart generated]" in out
