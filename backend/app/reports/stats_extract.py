"""Deterministic parser: verified-test stdout → structured stats fields.

The verified templates in `stats_engine.registry` print their results as labelled
lines (e.g. `T-statistic: -3.28`, `Cohen's d: -0.66`, `df: 98`). Those numbers are
scipy's — trustworthy — but only the p-value and test statistic get lifted into
the artifact `content` dict at run time; degrees of freedom, the effect-size VALUE,
the total N, and the per-group descriptives live only in the free-text `raw_output`.

Publication-grade (APA) reporting needs all of those. This module re-derives them
from the same deterministic stdout — no LLM, no re-running. It is used both:
  - at capture time (confirmatory.py) to persist structured fields on new artifacts, and
  - as a fallback when formatting OLDER artifacts that predate that capture.

Pure text parsing over a fixed, known output format → fully unit-testable offline.
"""
import re
from typing import Any, Optional

from app.stats_engine.registry import get_test

# registry effect-size name → (stdout label, APA symbol). A None label means the
# effect size IS the test statistic (correlation coefficients), so we read the
# statistic line instead.
_EFFECT_META: dict[str, tuple[Optional[str], str]] = {
    "cohens_d": ("Cohen's d", "d"),
    "eta_squared": ("Eta-squared", "η²"),        # η²
    "epsilon_squared": ("Epsilon-squared", "ε²"),  # ε²
    "cramers_v": ("Cramer's V", "V"),
    "rank_biserial_r": ("Effect size r", "r"),
    "odds_ratio": ("Odds ratio", "OR"),
    "r": (None, "r"),
    "rho": (None, "ρ"),                                # ρ
}

# test_name → (stdout label for the test statistic, APA symbol).
_STATISTIC_META: dict[str, tuple[str, str]] = {
    "pearson": ("Pearson r", "r"),
    "spearman": ("Spearman rho", "ρ"),
    "independent_t": ("T-statistic", "t"),
    "welch_t": ("T-statistic", "t"),
    "mann_whitney": ("U-statistic", "U"),
    "one_way_anova": ("F-statistic", "F"),
    "welch_anova": ("F-statistic", "F"),
    "kruskal_wallis": ("H-statistic", "H"),
    "chi_square": ("Chi-square statistic", "χ²"),   # χ²
    "fisher_exact": ("Odds ratio", "OR"),
}

_NUM = r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?"


def _find_float(label: str, text: str) -> Optional[float]:
    m = re.search(re.escape(label) + r":\s*(" + _NUM + r")", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_df(text: str) -> Optional[Any]:
    """Return None, a single float, or a [df1, df2] list for F-family tests.
    Reads the uniform `df:` line, falling back to chi-square's `Degrees of freedom:`."""
    m = re.search(r"(?m)^(?:df|Degrees of freedom):\s*([0-9.,\s]+?)\s*$", text)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    if not vals:
        return None
    return vals if len(vals) > 1 else vals[0]


def _extract_groups(text: str) -> list[dict[str, Any]]:
    """Per-group descriptives from either output shape:
       'Group 1 (control): mean=99.47, n=50'   (t-tests / Mann-Whitney), or
       '  north: mean=112.51, n=45'            (ANOVA / Kruskal, indented)."""
    groups: list[dict[str, Any]] = []
    for m in re.finditer(r"Group \d+ \((.+?)\): (mean|median)=(" + _NUM + r"), n=(\d+)", text):
        groups.append({"label": m.group(1), "center_type": m.group(2),
                       "center": float(m.group(3)), "n": int(m.group(4))})
    for m in re.finditer(r"(?m)^\s+(.+?): (mean|median)=(" + _NUM + r"), n=(\d+)\s*$", text):
        groups.append({"label": m.group(1).strip(), "center_type": m.group(2),
                       "center": float(m.group(3)), "n": int(m.group(4))})
    return groups


def extract_test_stats(test_name: Optional[str], raw_output: Optional[str]) -> dict[str, Any]:
    """Pull the publication-grade fields out of a verified test's stdout.

    Returns a dict with keys `df`, `n`, `statistic`, `effect_size`, `groups`.
    Any field that isn't present in the output is omitted (so callers can merge
    without clobbering values they already have). `effect_size`, when found, is
    {"name", "symbol", "value"}."""
    text = raw_output or ""
    out: dict[str, Any] = {}
    if not text.strip():
        return out

    entry = get_test(test_name) if test_name else None

    df = _extract_df(text)
    if df is not None:
        out["df"] = df

    groups = _extract_groups(text)
    if groups:
        out["groups"] = groups

    # Total N: prefer an explicit `N:` line, else sum the per-group sizes.
    n = None
    m = re.search(r"(?m)^N:\s*(\d+)\s*$", text)
    if m:
        n = int(m.group(1))
    elif groups:
        n = sum(g["n"] for g in groups)
    if n is not None:
        out["n"] = n

    # Test statistic (for the raw_output fallback path; confirmatory already
    # captures this at run time for the live path).
    if entry:
        stat_label, _ = _STATISTIC_META.get(test_name, (None, ""))
        if stat_label:
            stat = _find_float(stat_label, text)
            if stat is not None:
                out["statistic"] = stat

    # Effect size value + APA symbol.
    if entry:
        es_name = entry.get("effect_size")
        meta = _EFFECT_META.get(es_name) if es_name else None
        if meta:
            label, symbol = meta
            value = _find_float(label, text) if label else out.get("statistic")
            if value is None and label is None:
                # correlation coefficient: read the statistic line directly.
                stat_label, _ = _STATISTIC_META.get(test_name, (None, ""))
                value = _find_float(stat_label, text) if stat_label else None
            if value is not None:
                out["effect_size"] = {"name": es_name, "symbol": symbol, "value": value}

    return out
