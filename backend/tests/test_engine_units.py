"""Pure-logic golden tests: multiple-comparison correction, fuzzy test-name
resolution, and the assumption-aware override guard. No data, no network."""
import pytest

from app.reports.generator import _bh_adjust
from app.stats_engine.test_selector import resolve_requested_test
from app.regimes.confirmatory import _is_assumption_downgrade


# ── Benjamini-Hochberg FDR ───────────────────────────────────────────────────
class TestBenjaminiHochberg:
    def test_empty_and_single(self):
        assert _bh_adjust([]) == []
        assert _bh_adjust([0.2]) == [0.2]

    def test_all_equal_step_up(self):
        # p=[.01...05] -> every adjusted value is 0.05 (classic worked example).
        adj = _bh_adjust([0.01, 0.02, 0.03, 0.04, 0.05])
        assert all(abs(a - 0.05) < 1e-9 for a in adj)

    def test_preserves_input_order(self):
        # unsorted input; adjusted returned in the same positions.
        adj = _bh_adjust([0.9, 0.01, 0.5])
        assert [round(a, 4) for a in adj] == [0.9, 0.03, 0.75]

    def test_monotone_and_capped_at_one(self):
        adj = _bh_adjust([0.001, 0.5, 0.9, 0.99])
        assert all(0 <= a <= 1 for a in adj)
        # a very small raw p stays significant after correction
        assert adj[0] < 0.05


# ── Fuzzy test-name resolution ───────────────────────────────────────────────
class TestFuzzyTestName:
    @pytest.mark.parametrize("msg,expected", [
        ("run a t-test on x by y", "independent_t"),
        ("do a mann whitney", "mann_whitney"),
        ("man-whitney please", "mann_whitney"),        # typo
        ("use welch anova", "welch_anova"),             # longer alias beats 'welch'
        ("welchs t test", "welch_t"),
        ("chi squared test", "chi_square"),
        ("kruskal wallis", "kruskal_wallis"),
        ("run a pearson correlation", "pearson"),
        ("spearman rank correlation", "spearman"),
    ])
    def test_confident_matches(self, msg, expected):
        name, confident = resolve_requested_test(msg)
        assert name == expected and confident is True

    @pytest.mark.parametrize("msg", [
        "just plot it", "is that significant", "show me a histogram",
        "run a correlation between a and b",  # generic 'correlation' must NOT force a specific test
    ])
    def test_no_confident_override(self, msg):
        _, confident = resolve_requested_test(msg)
        assert confident is False


# ── Assumption-aware override guard ──────────────────────────────────────────
class TestOverrideGuard:
    @pytest.mark.parametrize("recommended,requested", [
        ("welch_t", "independent_t"),        # variance-robust -> equal-var
        ("welch_anova", "one_way_anova"),
        ("mann_whitney", "independent_t"),   # non-parametric -> parametric
        ("kruskal_wallis", "one_way_anova"),
        ("spearman", "pearson"),
    ])
    def test_keeps_engine_choice_on_downgrade(self, recommended, requested):
        assert _is_assumption_downgrade(recommended, requested) is True

    @pytest.mark.parametrize("recommended,requested", [
        ("independent_t", "mann_whitney"),   # user asks for MORE conservative -> allowed
        ("independent_t", "welch_t"),        # user asks for variance-robust -> allowed
        ("pearson", "spearman"),
        ("one_way_anova", "kruskal_wallis"),
    ])
    def test_allows_override_when_not_a_downgrade(self, recommended, requested):
        assert _is_assumption_downgrade(recommended, requested) is False
