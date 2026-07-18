"""Golden + unit tests for Goal 3 — publication-grade (APA) output.

Three layers, all offline (no E2B, no LLM, no DB, no network):
  1. df/N golden: the verified templates now print degrees of freedom (and total
     N where APA needs it); run them locally and assert the exact values.
  2. extractor: stdout → structured {df, n, statistic, effect_size, groups}.
  3. APA formatting: pure functions produce correct APA notation, Methods/Results
     prose, the summary table, and a well-formed LaTeX document.

Run: pytest tests/test_apa.py -v
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from tests import fixtures as F
from tests._local_sandbox import run_template_locally as run_tpl
from app.reports.stats_extract import extract_test_stats
from app.reports import apa


# ── helpers ───────────────────────────────────────────────────────────────────

def _art(content, variables=None, atype="test_result", aid=None):
    variables = variables or content.get("variables") or []
    return NS(id=aid or content.get("test_name", "a"), content=content,
              variables_involved=variables, artifact_type=atype, stage="inferential")


def _session():
    return NS(dataset_filename="trial_data.csv", hypothesis_text=None, hypothesis_columns=None)


# ── 1. df / N golden (real templates, local execution) ────────────────────────

class TestTemplateDegreesOfFreedom:
    def test_pearson_df_is_n_minus_2(self):
        out = run_tpl(F.two_numeric_normal(), "pearson", "height", "weight")
        assert extract_test_stats("pearson", out)["df"] == 88  # N=90

    def test_independent_t_df(self):
        out = run_tpl(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        assert extract_test_stats("independent_t", out)["df"] == 98  # 50+50-2

    def test_welch_t_df_is_fractional_satterthwaite(self):
        out = run_tpl(F.numeric_by_2group_unequalvar(), "welch_t", "bp", "arm")
        df = extract_test_stats("welch_t", out)["df"]
        assert isinstance(df, float) and 2 < df < 98  # Welch df is between 1 and n-2

    def test_one_way_anova_df_pair(self):
        out = run_tpl(F.numeric_by_3group_equalvar(), "one_way_anova", "bp", "region")
        ex = extract_test_stats("one_way_anova", out)
        assert ex["df"] == [2.0, 132.0]  # k-1=2, N-k=135-3=132
        assert ex["n"] == 135

    def test_welch_anova_df_pair(self):
        out = run_tpl(F.numeric_by_3group_unequalvar(), "welch_anova", "bp", "region")
        df = extract_test_stats("welch_anova", out)["df"]
        assert df[0] == 2.0 and isinstance(df[1], float)

    def test_kruskal_df_is_k_minus_1(self):
        out = run_tpl(F.numeric_by_3group_skewed(), "kruskal_wallis", "bp", "region")
        assert extract_test_stats("kruskal_wallis", out)["df"] == 2

    def test_chi_square_reports_df_and_total_n(self):
        out = run_tpl(F.two_categorical_2x2_adequate(), "chi_square", "sex", "passed")
        ex = extract_test_stats("chi_square", out)
        assert ex["df"] == 1
        assert ex["n"] == 200

    def test_mann_whitney_has_no_df(self):
        out = run_tpl(F.numeric_by_2group_skewed(), "mann_whitney", "bp", "arm")
        assert "df" not in extract_test_stats("mann_whitney", out)


# ── 2. extractor: effect sizes + group descriptives ──────────────────────────

class TestExtractor:
    def test_cohens_d_extracted_with_symbol(self):
        out = run_tpl(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        es = extract_test_stats("independent_t", out)["effect_size"]
        assert es["name"] == "cohens_d" and es["symbol"] == "d"
        assert isinstance(es["value"], float)

    def test_eta_squared_symbol(self):
        out = run_tpl(F.numeric_by_3group_equalvar(), "one_way_anova", "bp", "region")
        assert extract_test_stats("one_way_anova", out)["effect_size"]["symbol"] == "η²"

    def test_correlation_effect_is_the_coefficient(self):
        out = run_tpl(F.two_numeric_normal(), "pearson", "height", "weight")
        ex = extract_test_stats("pearson", out)
        assert ex["effect_size"]["value"] == ex["statistic"]  # r is both

    def test_groups_parsed_for_ttest(self):
        out = run_tpl(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        groups = extract_test_stats("independent_t", out)["groups"]
        assert {g["label"] for g in groups} == {"control", "treatment"}
        assert all(g["center_type"] == "mean" and g["n"] == 50 for g in groups)

    def test_groups_parsed_for_anova_indented(self):
        out = run_tpl(F.numeric_by_3group_equalvar(), "one_way_anova", "bp", "region")
        groups = extract_test_stats("one_way_anova", out)["groups"]
        assert {g["label"] for g in groups} == {"north", "south", "east"}

    def test_empty_output_yields_empty_dict(self):
        assert extract_test_stats("independent_t", "") == {}


# ── 3. APA number / notation formatting (pure) ───────────────────────────────

class TestApaFormatting:
    @pytest.mark.parametrize("p,expected", [
        (0.021, "*p* = .021"),
        (0.0005, "*p* < .001"),
        (0.9999, "*p* > .999"),
        (0.05, "*p* = .050"),
    ])
    def test_apa_p(self, p, expected):
        assert apa.apa_p(p) == expected

    def test_apa_p_latex(self):
        assert apa.apa_p(0.021, tex=True) == "$p$ = .021"

    @pytest.mark.parametrize("x,expected", [(0.34, ".34"), (-0.34, "-.34"), (1.0, "1.00"), (0.0, ".00")])
    def test_no_leading_zero(self, x, expected):
        assert apa._nlz(x) == expected

    @pytest.mark.parametrize("df,expected", [(88, "88"), (2.0, "2"), (54.48, "54.48"), (132.0, "132")])
    def test_fmt_df(self, df, expected):
        assert apa._fmt_df(df) == expected

    def test_ttest_notation(self):
        c = {"test_name": "independent_t", "df": 88, "statistic": 2.34, "p_value": 0.021,
             "effect_size": {"name": "cohens_d", "symbol": "d", "value": 0.50}}
        assert apa.apa_stat_string(c) == "*t*(88) = 2.34, *p* = .021, *d* = 0.50"

    def test_correlation_notation_no_duplicate_effect(self):
        c = {"test_name": "pearson", "df": 88, "statistic": 0.34, "p_value": 0.0009,
             "effect_size": {"name": "r", "symbol": "r", "value": 0.34}}
        assert apa.apa_stat_string(c) == "*r*(88) = .34, *p* < .001"

    def test_anova_notation_two_df(self):
        c = {"test_name": "one_way_anova", "df": [2, 87], "statistic": 5.2, "p_value": 0.007,
             "effect_size": {"name": "eta_squared", "symbol": "η²", "value": 0.11}}
        assert apa.apa_stat_string(c) == "*F*(2, 87) = 5.20, *p* = .007, *η²* = .11"

    def test_chi_square_notation_includes_n(self):
        c = {"test_name": "chi_square", "df": 1, "n": 200, "statistic": 5.78, "p_value": 0.016,
             "effect_size": {"name": "cramers_v", "symbol": "V", "value": 0.17}}
        assert apa.apa_stat_string(c) == "*χ²*(1, *N* = 200) = 5.78, *p* = .016, *V* = .17"

    def test_mann_whitney_notation_no_df(self):
        c = {"test_name": "mann_whitney", "statistic": 972.5, "p_value": 0.056,
             "effect_size": {"name": "rank_biserial_r", "symbol": "r", "value": 0.22}}
        assert apa.apa_stat_string(c) == "*U* = 972.50, *p* = .056, *r* = .22"

    def test_latex_notation_uses_math(self):
        c = {"test_name": "chi_square", "df": 1, "n": 200, "statistic": 5.78, "p_value": 0.016,
             "effect_size": {"name": "cramers_v", "symbol": "V", "value": 0.17}}
        assert apa.apa_stat_string(c, tex=True) == "$\\chi^2$(1, $N$ = 200) = 5.78, $p$ = .016, $V$ = .17"

    def test_raw_output_fallback_when_no_structured_fields(self):
        # An OLDER artifact that only has raw_output (no df/effect_size persisted).
        out = run_tpl(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        c = {"test_name": "independent_t", "statistic": -3.28, "p_value": 0.0014, "raw_output": out}
        s = apa.apa_stat_string(c)
        assert "*t*(98)" in s and "*d* =" in s  # reconstructed from raw_output


# ── 4. Results prose ─────────────────────────────────────────────────────────

class TestResultsProse:
    def test_significant_ttest_sentence(self):
        c = {"test_name": "independent_t", "display_name": "Independent Samples T-Test",
             "variables": ["bp", "arm"], "df": 98, "statistic": -3.28, "p_value": 0.0014,
             "effect_size": {"name": "cohens_d", "symbol": "d", "value": -0.66},
             "groups": [{"label": "control", "center_type": "mean", "center": 99.5, "n": 50},
                        {"label": "treatment", "center_type": "mean", "center": 107.2, "n": 50}]}
        s = apa._result_prose(c, sig=True, tex=False)
        assert "differed significantly" in s and "(*M* = 99.50, *n* = 50)" in s and "*t*(98) = -3.28" in s

    def test_nonsignificant_correlation_sentence(self):
        c = {"test_name": "pearson", "display_name": "Pearson Correlation", "variables": ["height", "income"],
             "df": 88, "statistic": 0.03, "p_value": 0.80,
             "effect_size": {"name": "r", "symbol": "r", "value": 0.03}}
        s = apa._result_prose(c, sig=False, tex=False)
        assert "did not reveal a significant relationship" in s

    def test_anova_posthoc_sentence(self):
        c = {"test_name": "one_way_anova", "display_name": "One-Way ANOVA", "variables": ["bp", "region"],
             "df": [2, 132], "statistic": 13.06, "p_value": 0.0001,
             "effect_size": {"name": "eta_squared", "symbol": "η²", "value": 0.17},
             "posthoc": {"method": "Tukey HSD", "comparisons": [
                 {"group_a": "north", "group_b": "south", "p_adj": 0.001, "significant": True}]}}
        s = apa._result_prose(c, sig=True, tex=False)
        assert "revealed a significant effect of region on bp" in s
        assert "Post-hoc comparisons (Tukey HSD)" in s and "north vs. south" in s


# ── 5. Methods, table, appendix, and top-level renderers ─────────────────────

def _sample_arts():
    t = {"test_name": "independent_t", "display_name": "Independent Samples T-Test",
         "variables": ["bp", "arm"], "df": 98, "statistic": -3.28, "p_value": 0.0014,
         "effect_size": {"name": "cohens_d", "symbol": "d", "value": -0.66},
         "assumption_results": {"normality_outcome": "pass", "variance_equal": "pass"},
         "engine_verified": True, "reasoning": "Groups were normal with equal variance.",
         "groups": [{"label": "control", "center_type": "mean", "center": 99.5, "n": 50},
                    {"label": "treatment", "center_type": "mean", "center": 107.2, "n": 50}]}
    chi = {"test_name": "chi_square", "display_name": "Chi-Square Test of Independence",
           "variables": ["sex", "passed"], "df": 1, "n": 200, "statistic": 5.78, "p_value": 0.016,
           "effect_size": {"name": "cramers_v", "symbol": "V", "value": 0.17},
           "assumption_results": {"min_expected_cell": "pass"}, "engine_verified": True}
    return [_art(t, aid="t"), _art(chi, aid="chi")]


class TestMethodsTableAppendix:
    def test_methods_mentions_procedures_and_correction(self):
        arts = _sample_arts()
        paras = apa._methods_paragraphs(arts, arts)
        text = "\n".join(paras)
        assert "Shapiro-Wilk" in text
        assert "Levene's test" in text
        assert "Benjamini-Hochberg" in text  # two tests → correction disclosed
        assert "α = .05" in text
        assert "SciPy" in text

    def test_summary_table_rows(self):
        arts = _sample_arts()
        rows = apa._summary_rows(arts, tex=False)
        assert len(rows) == 2
        trow = next(r for r in rows if "T-Test" in r["test"])
        assert trow["statistic"] == "*t*(98) = -3.28"
        assert trow["effect"] == "*d* = -0.66"

    def test_markdown_document_structure(self):
        arts = _sample_arts()
        md = apa.apa_markdown(_session(), arts, arts)
        assert "## Publication Write-up (APA style)" in md
        assert "### Method" in md and "### Results" in md
        assert "**Table 1**" in md
        assert "### Reproducibility Appendix" in md

    def test_reproducibility_lists_each_analysis(self):
        arts = _sample_arts()
        items = apa._reproducibility_items(arts)
        names = {it["display_name"] for it in items}
        assert names == {"Independent Samples T-Test", "Chi-Square Test of Independence"}
        assert all(it["verified"] == "verified" for it in items)


# ── 6. LaTeX document ────────────────────────────────────────────────────────

class TestLatex:
    def test_document_scaffold_and_escaping(self):
        c = {"test_name": "independent_t", "display_name": "T-Test",
             "variables": ["exam_score", "cohort"], "df": 98, "statistic": -3.28, "p_value": 0.0014,
             "effect_size": {"name": "cohens_d", "symbol": "d", "value": -0.66},
             "assumption_results": {"normality_outcome": "pass"}, "engine_verified": True,
             "groups": [{"label": "a", "center_type": "mean", "center": 1.0, "n": 5},
                        {"label": "b", "center_type": "mean", "center": 2.0, "n": 5}]}
        tex = apa.apa_latex(_session(), [_art(c)], [_art(c)])
        assert tex.startswith("\\documentclass")
        assert "\\begin{document}" in tex and "\\end{document}" in tex
        assert "exam\\_score" in tex          # underscore escaped
        assert "$\\alpha$ = .05" in tex        # unicode alpha → math
        assert "\\begin{tabular}" in tex       # summary table rendered

    def test_latex_math_symbols_for_chi_square(self):
        c = {"test_name": "chi_square", "display_name": "Chi", "variables": ["a", "b"],
             "df": 1, "n": 200, "statistic": 5.78, "p_value": 0.016,
             "effect_size": {"name": "cramers_v", "symbol": "V", "value": 0.17},
             "engine_verified": True}
        tex = apa.apa_latex(_session(), [_art(c)], [_art(c)])
        assert "$\\chi^2$" in tex

    def test_no_unescaped_percent_or_ampersand_outside_tables(self):
        # "95% CI" must be escaped to "95\%" everywhere it appears in prose.
        c = {"test_name": "linear_regression", "display_name": "Linear Regression",
             "model_type": "linear", "outcome": "score", "predictors": ["hours"],
             "n": 100, "r_squared": 0.5, "f_statistic": 98.0, "p_value": 1e-10,
             "engine_verified": True, "assumption_results": {},
             "coefficients": [{"name": "const", "coef": 1.0, "se": 0.1, "p_value": 0.5, "ci_low": 0.8, "ci_high": 1.2, "odds_ratio": None},
                              {"name": "hours", "coef": 4.0, "se": 0.1, "p_value": 1e-9, "ci_low": 3.8, "ci_high": 4.2, "odds_ratio": None}]}
        tex = apa.apa_latex(_session(), [_art(c)], [_art(c)])
        assert "95\\% CI" in tex


# ── 7. Integration: the real generate_report() (DB layer stubbed) ────────────

class TestGenerateReportIntegration:
    def _run(self, monkeypatch):
        from app.db.models import Session, Artifact
        from app.reports import generator

        now = datetime.now(timezone.utc)
        sid = uuid4()
        session = Session(id=sid, created_at=now, last_active_at=now, dataset_filename="trial.csv")

        def _mk(content, variables):
            return Artifact(id=uuid4(), session_id=sid, created_at=now, stage="inferential",
                            artifact_type="test_result", content=content, variables_involved=variables)

        # Real content built from a real template run through the real extractor.
        ttest_out = run_tpl(F.numeric_by_2group_equalvar(), "independent_t", "bp", "arm")
        ttest = _mk({"test_name": "independent_t", "display_name": "Independent Samples T-Test",
                     "variables": ["bp", "arm"], "p_value": 0.0014, "statistic": -3.28,
                     "engine_verified": True, "alpha": 0.05,
                     "assumption_results": {"normality_outcome": "pass", "variance_equal": "pass"},
                     "interpretation": "Groups differed.", "raw_output": ttest_out,
                     **extract_test_stats("independent_t", ttest_out)}, ["bp", "arm"])
        artifacts = [ttest]

        monkeypatch.setattr(generator, "get_session", lambda _sid: session)
        monkeypatch.setattr(generator, "get_artifacts_for_session",
                            lambda _sid, include_superseded=False: list(artifacts))
        return asyncio.run(generator.generate_report(str(sid)))

    def test_report_includes_apa_and_latex(self, monkeypatch):
        result = self._run(monkeypatch)
        md = result["markdown"]
        assert "## Publication Write-up (APA style)" in md
        assert "*t*(98) = -3.28" in md            # APA notation in the write-up
        assert "Shapiro-Wilk" in md               # methods prose
        assert result["latex"].startswith("\\documentclass")
        assert result["latex_filename"].endswith(".tex")
