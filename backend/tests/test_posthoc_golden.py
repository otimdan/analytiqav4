"""Golden tests for post-hoc pairwise comparisons — run the real templates
locally and check they identify which groups differ after a significant omnibus
test. No E2B, no network."""
import os
import pytest

from tests import fixtures as F
from tests._local_sandbox import write_csv, run_script
from app.stats_engine.registry import render_posthoc
from app.regimes.confirmatory import _parse_posthoc, _posthoc_summary
from app.reports.generator import _format_test_result


def _run_posthoc(df, key, outcome, grouping):
    code = render_posthoc(key, outcome, grouping)
    path = write_csv(df)
    try:
        return run_script(code, path)
    finally:
        os.remove(path)


class TestPosthocTemplates:
    @pytest.mark.parametrize("key", ["tukey", "games_howell", "dunn_bonferroni"])
    def test_runs_and_parses_all_pairs(self, key):
        out = _run_posthoc(F.numeric_by_3group_equalvar(), key, "bp", "region")
        assert "=== POSTHOC ===" in out
        parsed = _parse_posthoc(out, key)
        assert parsed is not None
        assert len(parsed["comparisons"]) == 3  # 3 groups -> 3 pairwise comparisons

    def test_identifies_the_clearly_different_pair(self):
        # region means north=100, south=106, east=112 -> north vs east clearly differ
        parsed = _parse_posthoc(_run_posthoc(F.numeric_by_3group_equalvar(), "tukey", "bp", "region"), "tukey")
        sig = {frozenset((c["group_a"], c["group_b"])) for c in parsed["comparisons"] if c["significant"]}
        assert frozenset(("north", "east")) in sig

    def test_adjusted_p_valid_range(self):
        parsed = _parse_posthoc(_run_posthoc(F.numeric_by_3group_skewed(), "dunn_bonferroni", "bp", "region"), "dunn_bonferroni")
        assert all(0.0 <= c["p_adj"] <= 1.0 for c in parsed["comparisons"])


def test_render_none_for_tests_without_posthoc():
    assert render_posthoc("pearson", "x", "y") is None
    assert render_posthoc("independent_t", "x", "y") is None


def test_summary_lists_only_significant():
    posthoc = {"method": "Tukey HSD", "comparisons": [
        {"group_a": "a", "group_b": "b", "p_adj": 0.01, "significant": True},
        {"group_a": "a", "group_b": "c", "p_adj": 0.40, "significant": False},
    ]}
    s = _posthoc_summary(posthoc)
    assert "a vs b" in s and "a vs c" not in s and "Tukey HSD" in s


def test_report_renders_posthoc_table():
    content = {
        "display_name": "One-Way ANOVA", "p_value": 0.01, "engine_verified": True,
        "posthoc": {"method": "Tukey HSD", "comparisons": [
            {"group_a": "north", "group_b": "east", "p_adj": 0.002, "significant": True},
        ]},
    }
    md = _format_test_result(content, "`bp` and `region`")
    assert "Post-hoc pairwise comparisons" in md and "north vs east" in md
