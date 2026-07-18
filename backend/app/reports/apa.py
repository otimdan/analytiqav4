"""Publication-grade (APA / journal-style) write-up, generated from verified
artifact metadata.

Everything here is a PURE function over the stored artifact `content` dicts — no
LLM, no sandbox, no DB. The verified engine already produced trustworthy numbers;
this module only *formats* them the way a journal expects:

  - correct APA notation:  t(88) = 2.34, p = .021, d = 0.50
  - an auto Methods section describing the tests + assumption procedures actually run
  - an APA Results section (one correct sentence per analysis, with post-hoc)
  - a formatted APA "Table 1" summarising every test
  - a Reproducibility appendix (exact tests, decisions, assumption outcomes, versions)

Two renderers share the same builders: `apa_markdown()` (folded into the .md
report) and `apa_latex()` (a standalone, copy-ready .tex document). Symbols are
rendered as markdown italics (`*t*`) or LaTeX math (`$t$`) via `_sym`.

Because it is pure, it is fully unit-testable offline (see tests/test_apa.py).
"""
import math
import platform
from importlib import metadata
from typing import Any, Optional

from app.reports.stats_extract import extract_test_stats

_FIELDS = ("df", "n", "statistic", "effect_size", "groups")

# unicode symbol → LaTeX math body. Used when tex=True.
_TEX_SYM = {
    "t": "t", "F": "F", "U": "U", "H": "H", "r": "r", "ρ": r"\rho",
    "χ²": r"\chi^2", "d": "d", "η²": r"\eta^2", "ε²": r"\varepsilon^2",
    "V": "V", "OR": r"\mathit{OR}", "p": "p", "N": "N", "M": "M",
    "Mdn": r"\mathit{Mdn}", "R²": "R^2", "B": "B", "SE": r"\mathit{SE}",
}

# test_name → (statistic symbol, APA singular description for Results prose).
_TEST_META = {
    "pearson": ("r", "A Pearson correlation"),
    "spearman": ("ρ", "A Spearman rank-order correlation"),
    "independent_t": ("t", "An independent-samples t-test"),
    "welch_t": ("t", "A Welch's independent-samples t-test"),
    "mann_whitney": ("U", "A Mann-Whitney U test"),
    "one_way_anova": ("F", "A one-way ANOVA"),
    "welch_anova": ("F", "A Welch's ANOVA"),
    "kruskal_wallis": ("H", "A Kruskal-Wallis H test"),
    "chi_square": ("χ²", "A chi-square test of independence"),
    "fisher_exact": ("OR", "A Fisher's exact test"),
}

# test_name → plural Methods description.
_METHODS_DESC = {
    "pearson": "Pearson product-moment correlations",
    "spearman": "Spearman rank-order correlations",
    "independent_t": "independent-samples t-tests",
    "welch_t": "Welch's independent-samples t-tests (which do not assume equal variances)",
    "mann_whitney": "Mann-Whitney U tests",
    "one_way_anova": "one-way analyses of variance (ANOVA)",
    "welch_anova": "Welch's analyses of variance",
    "kruskal_wallis": "Kruskal-Wallis H tests",
    "chi_square": "chi-square tests of independence",
    "fisher_exact": "Fisher's exact tests",
    "linear_regression": "multiple linear regression",
    "logistic_regression": "logistic regression",
}


# ── number / symbol formatting ────────────────────────────────────────────────

def _sym(u: str, tex: bool) -> str:
    """Render a statistical symbol as LaTeX math or markdown italic."""
    return ("$" + _TEX_SYM.get(u, u) + "$") if tex else ("*" + u + "*")


def _fmt(x: Optional[float], d: int = 2) -> str:
    """Plain fixed-decimal (keeps a leading zero): 0.66, -3.28."""
    return "—" if x is None else f"{x:.{d}f}"


def _nlz(x: Optional[float], d: int = 2) -> str:
    """APA no-leading-zero form for quantities bounded by ±1 (r, p, η², V, R²)."""
    if x is None:
        return "—"
    s = f"{x:.{d}f}"
    if s.startswith("0."):
        return s[1:]
    if s.startswith("-0."):
        return "-" + s[2:]
    return s


def _fmt_df(df: Any) -> str:
    """A single df: integer if whole (98), else two decimals (54.48)."""
    try:
        v = float(df)
    except (TypeError, ValueError):
        return str(df)
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def _p_cell(p: Optional[float]) -> str:
    """Bare APA p value for tables: .021, < .001, > .999."""
    if p is None:
        return "—"
    if p < 0.001:
        return "< .001"
    if p > 0.999:
        return "> .999"
    return _nlz(p, 3)


def apa_p(p: Optional[float], tex: bool = False) -> str:
    """Full APA p term: *p* = .021 / *p* < .001."""
    val = _p_cell(p)
    op = " " if val[0] in "<>" else " = "
    return _sym("p", tex) + op + val


# ── multiple-comparison correction (shared with the summary section) ──────────

def bh_adjust(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up FDR adjustment; returns adjusted p-values in the
    input order."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [1.0] * m
    min_so_far = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        val = pvals[idx] * m / rank
        min_so_far = min(min_so_far, val)
        adj[idx] = min(min_so_far, 1.0)
    return adj


# ── structured-stat access (content field, else raw_output fallback) ──────────

def _stats(content: dict[str, Any]) -> dict[str, Any]:
    """Publication fields for this test: prefer values persisted on the artifact,
    fall back to re-parsing the stored raw_output (older artifacts)."""
    out = {k: content[k] for k in _FIELDS if content.get(k) is not None}
    missing = [k for k in _FIELDS if k not in out]
    if missing:
        ex = extract_test_stats(content.get("test_name"), content.get("raw_output", ""))
        for k in missing:
            if ex.get(k) is not None:
                out[k] = ex[k]
    return out


# ── APA statistic string, e.g. "t(98) = -3.28, p = .001, d = -0.66" ───────────

def _components(content: dict[str, Any], tex: bool) -> tuple[str, str, str]:
    """(statistic_part, p_part, effect_part). Any part may be '' when N/A."""
    test = content.get("test_name") or ""
    st = _stats(content)
    stat_sym = (_TEST_META.get(test) or (None, ""))[0]
    value = st.get("statistic")
    df = st.get("df")
    n = st.get("n")
    es = st.get("effect_size")
    p_part = apa_p(content.get("p_value"), tex) if content.get("p_value") is not None else ""

    def es_part() -> str:
        if not es:
            return ""
        sym = es["symbol"]
        # variance-explained / correlation effect sizes drop the leading zero.
        val = _nlz(es["value"]) if sym in ("η²", "ε²", "V", "r", "ρ") else _fmt(es["value"])
        return f"{_sym(sym, tex)} = {val}"

    stat_part = ""
    if test in ("pearson", "spearman"):
        # coefficient IS the effect size — report it once, no separate d.
        stat_part = f"{_sym(stat_sym, tex)}({_fmt_df(df)}) = {_nlz(value)}" if df is not None else f"{_sym(stat_sym, tex)} = {_nlz(value)}"
        return stat_part, p_part, ""  # effect == statistic
    if test in ("independent_t", "welch_t"):
        stat_part = f"{_sym('t', tex)}({_fmt_df(df)}) = {_fmt(value)}"
    elif test in ("one_way_anova", "welch_anova"):
        if isinstance(df, (list, tuple)) and len(df) == 2:
            stat_part = f"{_sym('F', tex)}({_fmt_df(df[0])}, {_fmt_df(df[1])}) = {_fmt(value)}"
        else:
            stat_part = f"{_sym('F', tex)} = {_fmt(value)}"
    elif test == "kruskal_wallis":
        stat_part = f"{_sym('H', tex)}({_fmt_df(df)}) = {_fmt(value)}"
    elif test == "mann_whitney":
        stat_part = f"{_sym('U', tex)} = {_fmt(value)}"  # no df
    elif test == "chi_square":
        inner = f"{_fmt_df(df)}, {_sym('N', tex)} = {n}" if n is not None else _fmt_df(df)
        stat_part = f"{_sym('χ²', tex)}({inner}) = {_fmt(value)}"
    elif test == "fisher_exact":
        stat_part = ""  # only OR + p
    return stat_part, p_part, es_part()


def apa_stat_string(content: dict[str, Any], tex: bool = False) -> str:
    """The full inline APA statistic string for one test."""
    parts = [p for p in _components(content, tex) if p]
    return ", ".join(parts)


# ── Results prose ─────────────────────────────────────────────────────────────

def _center_symbol(groups: list[dict[str, Any]]) -> str:
    return "Mdn" if groups and groups[0].get("center_type") == "median" else "M"


def _two_group_descriptor(groups: list[dict[str, Any]], tex: bool) -> str:
    csym = _center_symbol(groups)
    g0, g1 = groups[0], groups[1]
    return (f"between {g0['label']} ({_sym(csym, tex)} = {_fmt(g0['center'])}, "
            f"{_sym('n', tex)} = {g0['n']}) and {g1['label']} "
            f"({_sym(csym, tex)} = {_fmt(g1['center'])}, {_sym('n', tex)} = {g1['n']})")


def _result_prose(content: dict[str, Any], sig: bool, tex: bool) -> str:
    """One full APA results sentence (statistic string embedded), incl. post-hoc."""
    test = content.get("test_name") or ""
    variables = content.get("variables") or []
    a = variables[0] if variables else "the first variable"
    b = variables[1] if len(variables) > 1 else "the second variable"
    desc = (_TEST_META.get(test) or (None, "An analysis"))[1]
    notation = apa_stat_string(content, tex)
    st = _stats(content)
    groups = st.get("groups") or []

    if test in ("independent_t", "welch_t", "mann_whitney"):
        gd = _two_group_descriptor(groups, tex) if len(groups) >= 2 else f"between the levels of {b}"
        verb = "differed significantly" if sig else "did not differ significantly"
        return f"{desc} indicated that {a} {verb} {gd}, {notation}."

    if test in ("one_way_anova", "welch_anova", "kruskal_wallis"):
        verb = "revealed a significant" if sig else "did not reveal a significant"
        sentence = f"{desc} {verb} effect of {b} on {a}, {notation}."
        return sentence + _posthoc_prose(content.get("posthoc"))

    if test in ("pearson", "spearman"):
        stat_val = st.get("statistic")
        direction = "positive" if (stat_val or 0) >= 0 else "negative"
        if sig:
            return f"{desc} revealed a significant {direction} relationship between {a} and {b}, {notation}."
        return f"{desc} did not reveal a significant relationship between {a} and {b}, {notation}."

    if test in ("chi_square", "fisher_exact"):
        verb = "revealed a significant" if sig else "did not reveal a significant"
        return f"{desc} {verb} association between {a} and {b}, {notation}."

    # Unknown test: still emit the notation.
    return f"{desc}: {notation}." if notation else f"{desc} was performed."


def _posthoc_prose(posthoc: Optional[dict[str, Any]]) -> str:
    if not posthoc or not posthoc.get("comparisons"):
        return ""
    method = posthoc.get("method", "post-hoc")
    sig = [f"{c['group_a']} vs. {c['group_b']}" for c in posthoc["comparisons"] if c.get("significant")]
    if sig:
        return f" Post-hoc comparisons ({method}) indicated significant differences between {_oxford(sig)}."
    return f" Post-hoc comparisons ({method}) revealed no significant pairwise differences after correction."


def _oxford(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ── Regression Results prose + coefficient rows ───────────────────────────────

def _regression_prose(content: dict[str, Any], tex: bool) -> str:
    outcome = content.get("outcome", "the outcome")
    predictors = content.get("predictors") or []
    pred_str = _oxford([str(p) for p in predictors]) if predictors else "the predictors"
    coefs = [c for c in (content.get("coefficients") or []) if c.get("name") != "const"]
    is_log = content.get("model_type") == "logistic"
    model_p = content.get("p_value")

    if is_log:
        lead = f"A logistic regression was conducted to model {outcome} from {pred_str}."
        r2 = content.get("r_squared")
        fit = f" The model's McFadden pseudo-{_sym('R²', tex)} was {_nlz(r2)}" + (f", {apa_p(model_p, tex)}." if model_p is not None else ".") if r2 is not None else ""
        sig_preds = []
        for c in coefs:
            if c.get("p_value") is not None and c["p_value"] < 0.05 and c.get("odds_ratio") is not None:
                orv = c["odds_ratio"]
                ci = ""
                if c.get("ci_low") is not None and c.get("ci_high") is not None:
                    ci = f", 95% CI [{_fmt(math.exp(c['ci_low']))}, {_fmt(math.exp(c['ci_high']))}]"
                dirn = "higher" if orv >= 1 else "lower"
                sig_preds.append(f"{c['name']} was associated with {dirn} odds of the outcome "
                                 f"({_sym('OR', tex)} = {_fmt(orv)}{ci}, {apa_p(c['p_value'], tex)})")
        tail = (" " + _oxford(sig_preds).capitalize() + ".") if sig_preds else " No predictor reached significance."
        return lead + fit + tail

    # linear
    r2 = content.get("r_squared")
    f_stat = content.get("f_statistic")
    n = content.get("n")
    k = len(coefs)
    df_tail = ""
    if f_stat is not None and n is not None:
        df1, df2 = k, n - (k + 1)
        df_tail = f", {_sym('F', tex)}({df1}, {df2}) = {_fmt(f_stat)}"
    sig_model = model_p is not None and model_p < 0.05
    verb = "explained a significant proportion of variance in" if sig_model else "did not explain a significant proportion of variance in"
    fit = (f" The model {verb} {outcome}, {_sym('R²', tex)} = {_nlz(r2)}{df_tail}"
           + (f", {apa_p(model_p, tex)}." if model_p is not None else "."))
    sig_preds = []
    for c in coefs:
        if c.get("p_value") is not None and c["p_value"] < 0.05:
            ci = ""
            if c.get("ci_low") is not None and c.get("ci_high") is not None:
                ci = f", 95% CI [{_fmt(c['ci_low'])}, {_fmt(c['ci_high'])}]"
            sig_preds.append(f"{c['name']} ({_sym('B', tex)} = {_fmt(c['coef'])}{ci}, {apa_p(c['p_value'], tex)})")
    lead = f"A multiple linear regression was conducted to predict {outcome} from {pred_str}."
    tail = (" Significant predictors were " + _oxford(sig_preds) + ".") if sig_preds else " No individual predictor reached significance."
    return lead + fit + tail


# ── Significance bookkeeping (adjusted p when >1 verified test) ────────────────

def _significance_map(test_results: list) -> dict[str, bool]:
    """artifact.id → is-significant, using BH-adjusted p across the verified tests
    when more than one was run (matches the report's summary section)."""
    verified_with_p = [a for a in test_results
                       if (a.content or {}).get("engine_verified", True)
                       and (a.content or {}).get("p_value") is not None]
    result: dict[str, bool] = {}
    if len(verified_with_p) > 1:
        adj = bh_adjust([float(a.content["p_value"]) for a in verified_with_p])
        for a, ap in zip(verified_with_p, adj):
            result[str(a.id)] = ap < 0.05
    for a in test_results:
        if str(a.id) not in result:
            p = (a.content or {}).get("p_value")
            result[str(a.id)] = (p is not None and p < 0.05)
    return result


def _is_regression(content: dict[str, Any]) -> bool:
    return bool(content.get("coefficients")) or str(content.get("test_name", "")).endswith("_regression")


# ── Methods ───────────────────────────────────────────────────────────────────

def _methods_paragraphs(artifacts: list, test_results: list) -> list[str]:
    paras: list[str] = []
    verified_names = [(a.content or {}).get("test_name") for a in test_results
                     if (a.content or {}).get("engine_verified", True)]
    verified_names = [n for n in verified_names if n]

    # 1. Data preparation (from cleaning artifacts).
    ops: list[str] = []
    for a in artifacts:
        if a.artifact_type == "cleaned_dataset":
            ops.extend((a.content or {}).get("operations_applied", []) or [])
    if ops:
        paras.append("Prior to analysis, the data were prepared using the following steps: "
                     + _oxford([str(o) for o in ops]) + ".")

    # 2. The tests that were run, described once per unique type.
    seen: list[str] = []
    for n in verified_names:
        if n not in seen:
            seen.append(n)
    if seen:
        described = _oxford([_METHODS_DESC.get(n, n) for n in seen])
        paras.append(f"Analyses comprised {described}.")

    # 3. Assumption procedures actually exercised (truthful to the live checks).
    checks_present = set()
    for a in test_results:
        for key, val in ((a.content or {}).get("assumption_results") or {}).items():
            if val in ("pass", "fail"):
                checks_present.add(key)
    assumption_sentences = []
    if any(k.startswith("normality") for k in checks_present):
        assumption_sentences.append("normality was assessed using the Shapiro-Wilk test "
                                    "(D'Agostino's K² test for larger samples), and a "
                                    "non-parametric alternative was used where it was violated")
    if "variance_equal" in checks_present:
        assumption_sentences.append("homogeneity of variance was assessed using Levene's test")
    if "min_expected_cell" in checks_present:
        assumption_sentences.append("minimum expected cell frequencies were checked, with "
                                    "Fisher's exact test substituted when they were too low")
    if assumption_sentences:
        paras.append("Test assumptions were checked before each analysis: "
                     + "; ".join(assumption_sentences) + ".")

    # 4. Multiple comparisons.
    n_verified_p = len([a for a in test_results
                        if (a.content or {}).get("engine_verified", True)
                        and (a.content or {}).get("p_value") is not None])
    if n_verified_p > 1:
        paras.append("Because multiple comparisons were performed, p-values were adjusted "
                     "using the Benjamini-Hochberg false discovery rate procedure.")

    # 5. Software + alpha.
    v = software_versions()
    has_reg = any(_is_regression(a.content or {}) for a in test_results)
    libs = [f"SciPy (v{v['scipy']})"]
    if has_reg:
        libs.append(f"statsmodels (v{v['statsmodels']})")
    libs += [f"NumPy (v{v['numpy']})", f"pandas (v{v['pandas']})"]
    paras.append(f"All analyses were conducted in Python {v['python']} using "
                 + _oxford(libs) + ". Statistical significance was evaluated at α = .05.")
    return paras


# ── Reproducibility appendix ──────────────────────────────────────────────────

def software_versions() -> dict[str, str]:
    def ver(pkg: str) -> str:
        try:
            return metadata.version(pkg)
        except Exception:
            return "unknown"
    return {
        "python": platform.python_version(),
        "scipy": ver("scipy"), "statsmodels": ver("statsmodels"),
        "numpy": ver("numpy"), "pandas": ver("pandas"),
    }


def _reproducibility_items(test_results: list) -> list[dict[str, str]]:
    items = []
    for a in test_results:
        c = a.content or {}
        checks = {k: val for k, val in (c.get("assumption_results") or {}).items()
                  if val in ("pass", "fail")}
        items.append({
            "display_name": c.get("display_name", "Analysis"),
            "test_name": c.get("test_name", ""),
            "variables": ", ".join(c.get("variables") or a.variables_involved or []),
            "verified": "verified" if c.get("engine_verified", True) else "assisted (unverified)",
            "reasoning": c.get("reasoning", ""),
            "assumptions": "; ".join(f"{k} = {val}" for k, val in checks.items()),
        })
    return items


# ── Summary table rows ────────────────────────────────────────────────────────

def _summary_rows(test_results: list, tex: bool) -> list[dict[str, str]]:
    sig_map = _significance_map(test_results)
    rows = []
    for a in test_results:
        c = a.content or {}
        if _is_regression(c):
            continue  # regression gets its own coefficient table
        stat_part, _, es_part = _components(c, tex)
        rows.append({
            "test": c.get("display_name", "Test"),
            "variables": ", ".join(c.get("variables") or a.variables_involved or []),
            "statistic": stat_part or "—",
            "p": _p_cell(c.get("p_value")),
            "effect": es_part or "—",
            "sig": "Yes" if sig_map.get(str(a.id)) else "No",
        })
    return rows


# ── Markdown renderer ─────────────────────────────────────────────────────────

def apa_markdown(session, artifacts: list, test_results: list) -> str:
    sig_map = _significance_map(test_results)
    out: list[str] = ["## Publication Write-up (APA style)",
                      "*Auto-generated from the verified analysis metadata. "
                      "Review before submission.*"]

    methods = _methods_paragraphs(artifacts, test_results)
    if methods:
        out.append("### Method")
        out.extend(methods)

    if test_results:
        out.append("### Results")
        for a in test_results:
            c = a.content or {}
            if _is_regression(c):
                prose = _regression_prose(c, tex=False)
            else:
                prose = _result_prose(c, sig_map.get(str(a.id), False), tex=False)
            label = c.get("display_name", "Analysis")
            badge = "" if c.get("engine_verified", True) else " *(assisted, unverified)*"
            out.append(f"**{label}.**{badge} {prose}")

        rows = _summary_rows(test_results, tex=False)
        if rows:
            out.append("**Table 1**")
            out.append("*Summary of Statistical Analyses*")
            out.append("| Analysis | Variables | Statistic | *p* | Effect size | Significant |")
            out.append("|----------|-----------|-----------|-----|-------------|-------------|")
            for r in rows:
                out.append(f"| {r['test']} | {r['variables']} | {r['statistic']} | {r['p']} | {r['effect']} | {r['sig']} |")

        # Regression coefficient tables.
        for a in test_results:
            c = a.content or {}
            if _is_regression(c) and c.get("coefficients"):
                out.append(_regression_table_md(c))

    out.append("### Reproducibility Appendix")
    v = software_versions()
    out.append(f"**Software.** Python {v['python']}; SciPy {v['scipy']}; "
               f"statsmodels {v['statsmodels']}; NumPy {v['numpy']}; pandas {v['pandas']}.")
    items = _reproducibility_items(test_results)
    if items:
        out.append("**Analyses performed.**")
        for it in items:
            line = f"- *{it['display_name']}* ({it['variables']}) — {it['verified']}."
            if it["assumptions"]:
                line += f" Assumption checks: {it['assumptions']}."
            if it["reasoning"]:
                line += f" {it['reasoning']}"
            out.append(line)
    return "\n\n".join(out)


def _regression_table_md(c: dict[str, Any]) -> str:
    is_log = c.get("model_type") == "logistic"
    lines = [f"**{c.get('display_name', 'Regression')} — coefficients**", ""]
    if is_log:
        lines.append("| Predictor | *B* | *SE* | *OR* | 95% CI (OR) | *p* |")
        lines.append("|-----------|-----|------|------|-------------|-----|")
        for co in c["coefficients"]:
            orv = co.get("odds_ratio")
            ci = f"[{_fmt(math.exp(co['ci_low']))}, {_fmt(math.exp(co['ci_high']))}]" if co.get("ci_low") is not None else "—"
            lines.append(f"| {co['name']} | {_fmt(co['coef'])} | {_fmt(co.get('se'))} | {_fmt(orv) if orv is not None else '—'} | {ci} | {_p_cell(co.get('p_value'))} |")
    else:
        lines.append("| Predictor | *B* | *SE* | 95% CI | *p* |")
        lines.append("|-----------|-----|------|--------|-----|")
        for co in c["coefficients"]:
            ci = f"[{_fmt(co['ci_low'])}, {_fmt(co['ci_high'])}]" if co.get("ci_low") is not None else "—"
            lines.append(f"| {co['name']} | {_fmt(co['coef'])} | {_fmt(co.get('se'))} | {ci} | {_p_cell(co.get('p_value'))} |")
    return "\n".join(lines)


# ── LaTeX renderer ────────────────────────────────────────────────────────────

_TEX_ESCAPE = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
               "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
               "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
               # unicode that pdflatex can't set in text mode → safe equivalents
               "α": r"$\alpha$", "—": "---", "–": "--", "≥": r"$\geq$", "≤": r"$\leq$"}


def _esc(text: str) -> str:
    """Escape LaTeX specials in dynamic (non-math) text — column names, labels."""
    return "".join(_TEX_ESCAPE.get(ch, ch) for ch in str(text))


def _tex_inline(md: str) -> str:
    """Render a builder string that already contains LaTeX math ($...$) plus plain
    prose. Escape only OUTSIDE the math spans so \\rho etc. survive."""
    parts = md.split("$")
    out = []
    for i, seg in enumerate(parts):
        # odd indices sit inside a math span — keep verbatim and re-wrap in $...$
        out.append(("$" + seg + "$") if i % 2 == 1 else _esc(seg))
    return "".join(out)


def apa_latex(session, artifacts: list, test_results: list) -> str:
    sig_map = _significance_map(test_results)
    dataset = _esc(getattr(session, "dataset_filename", None) or "Dataset")
    L: list[str] = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{amssymb,amsmath}",
        r"\usepackage{booktabs}",
        r"\usepackage{array}",
        r"\title{Statistical Analysis Report}",
        r"\author{}",
        r"\date{Dataset: " + dataset + r"}",
        r"\begin{document}",
        r"\maketitle",
        r"\emph{Auto-generated from verified analysis metadata. Review before submission.}",
    ]

    methods = _methods_paragraphs(artifacts, test_results)
    if methods:
        L.append(r"\section*{Method}")
        for para in methods:
            L.append(_tex_inline(para))

    if test_results:
        L.append(r"\section*{Results}")
        for a in test_results:
            c = a.content or {}
            prose = _regression_prose(c, tex=True) if _is_regression(c) else _result_prose(c, sig_map.get(str(a.id), False), tex=True)
            label = _esc(c.get("display_name", "Analysis"))
            L.append(r"\noindent\textbf{" + label + r".} " + _tex_inline(prose))

        rows = _summary_rows(test_results, tex=True)
        if rows:
            L.append(r"\bigskip\noindent\textbf{Table 1.} \emph{Summary of Statistical Analyses}")
            L.append(r"\begin{center}\begin{tabular}{l l l l l l}")
            L.append(r"\toprule")
            L.append(r"Analysis & Variables & Statistic & $p$ & Effect size & Sig. \\")
            L.append(r"\midrule")
            for r in rows:
                L.append(" & ".join([
                    _esc(r["test"]), _esc(r["variables"]),
                    _tex_inline(r["statistic"]), _esc(r["p"]),
                    _tex_inline(r["effect"]), _esc(r["sig"]),
                ]) + r" \\")
            L.append(r"\bottomrule")
            L.append(r"\end{tabular}\end{center}")

        for a in test_results:
            c = a.content or {}
            if _is_regression(c) and c.get("coefficients"):
                L.append(_regression_table_tex(c))

    L.append(r"\section*{Reproducibility Appendix}")
    v = software_versions()
    L.append(r"\noindent\textbf{Software.} " + _esc(
        f"Python {v['python']}; SciPy {v['scipy']}; statsmodels {v['statsmodels']}; "
        f"NumPy {v['numpy']}; pandas {v['pandas']}.") )
    items = _reproducibility_items(test_results)
    if items:
        L.append(r"\begin{itemize}")
        for it in items:
            line = f"\\textit{{{_esc(it['display_name'])}}} ({_esc(it['variables'])}) --- {_esc(it['verified'])}."
            if it["assumptions"]:
                line += " Assumption checks: " + _esc(it["assumptions"]) + "."
            if it["reasoning"]:
                line += " " + _esc(it["reasoning"])
            L.append(r"\item " + line)
        L.append(r"\end{itemize}")

    L.append(r"\end{document}")
    return "\n".join(L)


def _regression_table_tex(c: dict[str, Any]) -> str:
    is_log = c.get("model_type") == "logistic"
    head = _esc(c.get("display_name", "Regression"))
    L = [r"\bigskip\noindent\textbf{" + head + r" --- coefficients}", r"\begin{center}"]
    if is_log:
        L.append(r"\begin{tabular}{l r r r l r}")
        L.append(r"\toprule")
        L.append(r"Predictor & $B$ & $\mathit{SE}$ & $\mathit{OR}$ & 95\% CI (OR) & $p$ \\")
        L.append(r"\midrule")
        for co in c["coefficients"]:
            orv = co.get("odds_ratio")
            ci = f"[{_fmt(math.exp(co['ci_low']))}, {_fmt(math.exp(co['ci_high']))}]" if co.get("ci_low") is not None else "—"
            L.append(" & ".join([_esc(co["name"]), _fmt(co["coef"]), _fmt(co.get("se")),
                                 _fmt(orv) if orv is not None else "—", _esc(ci), _esc(_p_cell(co.get("p_value")))]) + r" \\")
    else:
        L.append(r"\begin{tabular}{l r r l r}")
        L.append(r"\toprule")
        L.append(r"Predictor & $B$ & $\mathit{SE}$ & 95\% CI & $p$ \\")
        L.append(r"\midrule")
        for co in c["coefficients"]:
            ci = f"[{_fmt(co['ci_low'])}, {_fmt(co['ci_high'])}]" if co.get("ci_low") is not None else "—"
            L.append(" & ".join([_esc(co["name"]), _fmt(co["coef"]), _fmt(co.get("se")),
                                 _esc(ci), _esc(_p_cell(co.get("p_value")))]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(L)
