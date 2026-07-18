from typing import Any

SUPPORTED_TESTS: list[dict[str, Any]] = [
    {
        "test_name": "pearson", "display_name": "Pearson Correlation", "category": "correlation",
        "required_types": ["numeric", "numeric"], "min_groups": None, "max_groups": None,
        "assumptions": ["normality_a", "normality_b"], "nonparametric": False, "code_template": "pearson",
        "interpretation": "The Pearson r coefficient ranges from -1 to 1. A p-value below 0.05 suggests the linear relationship is unlikely to be due to chance.",
        "effect_size": "r", "posthoc": None,
    },
    {
        "test_name": "spearman", "display_name": "Spearman Rank Correlation", "category": "correlation",
        "required_types": ["numeric_or_ordinal", "numeric_or_ordinal"], "min_groups": None, "max_groups": None,
        "assumptions": [], "nonparametric": True, "code_template": "spearman",
        "interpretation": "Spearman's rho measures how consistently one variable increases as the other increases, without assuming a linear relationship.",
        "effect_size": "rho", "posthoc": None,
    },
    {
        "test_name": "independent_t", "display_name": "Independent Samples T-Test", "category": "group_comparison",
        "required_types": ["numeric", "categorical"], "min_groups": 2, "max_groups": 2,
        "assumptions": ["normality_outcome", "variance_equal"], "nonparametric": False, "code_template": "independent_t",
        "interpretation": "The t-test compares the means of two groups. A p-value below 0.05 suggests the difference in means is unlikely to be due to chance.",
        "effect_size": "cohens_d", "posthoc": None,
    },
    {
        "test_name": "welch_t", "display_name": "Welch's T-Test", "category": "group_comparison",
        "required_types": ["numeric", "categorical"], "min_groups": 2, "max_groups": 2,
        "assumptions": ["normality_outcome"], "nonparametric": False, "code_template": "welch_t",
        "interpretation": "Welch's t-test does not assume equal variance between groups. It is more reliable when group sizes or spreads differ.",
        "effect_size": "cohens_d", "posthoc": None,
    },
    {
        "test_name": "mann_whitney", "display_name": "Mann-Whitney U Test", "category": "group_comparison",
        "required_types": ["numeric_or_ordinal", "categorical"], "min_groups": 2, "max_groups": 2,
        "assumptions": [], "nonparametric": True, "code_template": "mann_whitney",
        "interpretation": "The Mann-Whitney U test compares the distributions of two groups without assuming normality.",
        "effect_size": "rank_biserial_r", "posthoc": None,
    },
    {
        "test_name": "one_way_anova", "display_name": "One-Way ANOVA", "category": "group_comparison",
        "required_types": ["numeric", "categorical"], "min_groups": 3, "max_groups": None,
        "assumptions": ["normality_outcome", "variance_equal"], "nonparametric": False, "code_template": "one_way_anova",
        "interpretation": "One-way ANOVA tests whether the mean differs across three or more groups.",
        "effect_size": "eta_squared", "posthoc": "tukey",
    },
    {
        "test_name": "welch_anova", "display_name": "Welch's ANOVA", "category": "group_comparison",
        "required_types": ["numeric", "categorical"], "min_groups": 3, "max_groups": None,
        "assumptions": ["normality_outcome"], "nonparametric": False, "code_template": "welch_anova",
        "interpretation": "Welch's ANOVA is preferred when group variances are unequal.",
        "effect_size": "eta_squared", "posthoc": "games_howell",
    },
    {
        "test_name": "kruskal_wallis", "display_name": "Kruskal-Wallis Test", "category": "group_comparison",
        "required_types": ["numeric_or_ordinal", "categorical"], "min_groups": 3, "max_groups": None,
        "assumptions": [], "nonparametric": True, "code_template": "kruskal_wallis",
        "interpretation": "Kruskal-Wallis is the non-parametric equivalent of one-way ANOVA.",
        "effect_size": "epsilon_squared", "posthoc": "dunn_bonferroni",
    },
    {
        "test_name": "chi_square", "display_name": "Chi-Square Test of Independence", "category": "categorical_association",
        "required_types": ["categorical", "categorical"], "min_groups": None, "max_groups": None,
        "assumptions": ["min_expected_cell"], "nonparametric": True, "code_template": "chi_square",
        "interpretation": "Chi-square tests whether two categorical variables are independent of each other.",
        "effect_size": "cramers_v", "posthoc": None,
    },
    {
        "test_name": "fisher_exact", "display_name": "Fisher's Exact Test", "category": "categorical_association",
        "required_types": ["categorical", "categorical"], "min_groups": None, "max_groups": None,
        "assumptions": [], "nonparametric": True, "code_template": "fisher_exact",
        "interpretation": "Fisher's exact test is used instead of chi-square when expected cell counts are small.",
        "effect_size": "odds_ratio", "posthoc": None,
    },
]

TEST_BY_NAME: dict[str, dict[str, Any]] = {t["test_name"]: t for t in SUPPORTED_TESTS}


def get_test(test_name: str) -> dict[str, Any] | None:
    return TEST_BY_NAME.get(test_name)


def get_all_test_names() -> list[str]:
    return list(TEST_BY_NAME.keys())


# Deterministic test code. These are executed DIRECTLY (no LLM code-gen) so the
# number the user sees is always scipy's number, not an LLM's impression of it.
#
# Column names are attacker-controlled (they come from the uploaded CSV header),
# so they are NEVER string-interpolated as raw text. Instead the templates carry
# sentinel tokens (__COL_A__, __OUTCOME__, ...) that `render_template` replaces
# with the repr() of the real column name. Sentinels (not str.format) are used so
# the f-string braces inside these scripts (e.g. {r:.4f}) are left untouched.
CODE_TEMPLATES: dict[str, str] = {
    "pearson": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
x = df[__COL_A__].dropna()
y = df[__COL_B__].dropna()
common = x.index.intersection(y.index)
x, y = x[common], y[common]
r, p = stats.pearsonr(x, y)
print(f"Pearson r: {r:.4f}")
print(f"P-value: {p:.4f}")
print(f"N: {len(x)}")
print(f"df: {len(x) - 2}")
""",
    "spearman": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
x = df[__COL_A__].dropna()
y = df[__COL_B__].dropna()
common = x.index.intersection(y.index)
x, y = x[common], y[common]
rho, p = stats.spearmanr(x, y)
print(f"Spearman rho: {rho:.4f}")
print(f"P-value: {p:.4f}")
print(f"N: {len(x)}")
print(f"df: {len(x) - 2}")
""",
    "independent_t": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = df[__GROUPING__].dropna().unique()
g1 = df[df[__GROUPING__] == groups[0]][__OUTCOME__].dropna()
g2 = df[df[__GROUPING__] == groups[1]][__OUTCOME__].dropna()
t, p = stats.ttest_ind(g1, g2, equal_var=True)
pooled_std = np.sqrt(((len(g1)-1)*g1.std()**2 + (len(g2)-1)*g2.std()**2) / (len(g1)+len(g2)-2))
d = (g1.mean() - g2.mean()) / pooled_std
print(f"Group 1 ({groups[0]}): mean={g1.mean():.4f}, n={len(g1)}")
print(f"Group 2 ({groups[1]}): mean={g2.mean():.4f}, n={len(g2)}")
print(f"T-statistic: {t:.4f}")
print(f"P-value: {p:.4f}")
print(f"Cohen's d: {d:.4f}")
print(f"df: {len(g1) + len(g2) - 2}")
""",
    "welch_t": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = df[__GROUPING__].dropna().unique()
g1 = df[df[__GROUPING__] == groups[0]][__OUTCOME__].dropna()
g2 = df[df[__GROUPING__] == groups[1]][__OUTCOME__].dropna()
t, p = stats.ttest_ind(g1, g2, equal_var=False)
pooled_std = np.sqrt(((len(g1)-1)*g1.std()**2 + (len(g2)-1)*g2.std()**2) / (len(g1)+len(g2)-2))
d = (g1.mean() - g2.mean()) / pooled_std
v1, v2 = g1.var(ddof=1), g2.var(ddof=1)
n1, n2 = len(g1), len(g2)
welch_df = (v1/n1 + v2/n2)**2 / ((v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1))
print(f"Group 1 ({groups[0]}): mean={g1.mean():.4f}, n={len(g1)}")
print(f"Group 2 ({groups[1]}): mean={g2.mean():.4f}, n={len(g2)}")
print(f"T-statistic: {t:.4f}")
print(f"P-value: {p:.4f}")
print(f"Cohen's d: {d:.4f}")
print(f"df: {welch_df:.2f}")
""",
    "mann_whitney": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = df[__GROUPING__].dropna().unique()
g1 = df[df[__GROUPING__] == groups[0]][__OUTCOME__].dropna()
g2 = df[df[__GROUPING__] == groups[1]][__OUTCOME__].dropna()
u, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
r = 1 - (2 * u) / (len(g1) * len(g2))
print(f"Group 1 ({groups[0]}): median={g1.median():.4f}, n={len(g1)}")
print(f"Group 2 ({groups[1]}): median={g2.median():.4f}, n={len(g2)}")
print(f"U-statistic: {u:.4f}")
print(f"P-value: {p:.4f}")
print(f"Effect size r: {r:.4f}")
""",
    "kruskal_wallis": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = [group[__OUTCOME__].dropna() for _, group in df.groupby(__GROUPING__)]
group_labels = df[__GROUPING__].dropna().unique()
h, p = stats.kruskal(*groups)
n = sum(len(g) for g in groups)
epsilon_sq = (h - len(groups) + 1) / (n - len(groups))
print(f"H-statistic: {h:.4f}")
print(f"P-value: {p:.4f}")
print(f"Epsilon-squared: {epsilon_sq:.4f}")
print(f"df: {len(groups) - 1}")
print(f"N: {n}")
for label, g in zip(group_labels, groups):
    print(f"  {label}: median={g.median():.4f}, n={len(g)}")
""",
    "chi_square": """
import pandas as pd
from scipy import stats
import numpy as np
df = pd.read_csv('/home/user/data.csv')
contingency = pd.crosstab(df[__COL_A__], df[__COL_B__])
chi2, p, dof, expected = stats.chi2_contingency(contingency)
n = contingency.values.sum()
cramers_v = np.sqrt(chi2 / (n * (min(contingency.shape) - 1)))
print(f"Chi-square statistic: {chi2:.4f}")
print(f"P-value: {p:.4f}")
print(f"Degrees of freedom: {dof}")
print(f"Cramer's V: {cramers_v:.4f}")
print(f"N: {int(n)}")
""",
    "fisher_exact": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
contingency = pd.crosstab(df[__COL_A__], df[__COL_B__])
if contingency.shape != (2, 2):
    print("Fisher's exact test requires a 2x2 table.")
    print("Your table shape:", contingency.shape)
else:
    odds_ratio, p = stats.fisher_exact(contingency.values)
    print(f"Odds ratio: {odds_ratio:.4f}")
    print(f"P-value: {p:.4f}")
""",
    "one_way_anova": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = [group[__OUTCOME__].dropna() for _, group in df.groupby(__GROUPING__)]
group_labels = df[__GROUPING__].dropna().unique()
f, p = stats.f_oneway(*groups)
grand_mean = df[__OUTCOME__].mean()
ss_between = sum(len(g) * (g.mean() - grand_mean)**2 for g in groups)
ss_total = sum((df[__OUTCOME__].dropna() - grand_mean)**2)
eta_sq = ss_between / ss_total
_n_total = sum(len(g) for g in groups)
print(f"F-statistic: {f:.4f}")
print(f"P-value: {p:.4f}")
print(f"Eta-squared: {eta_sq:.4f}")
print(f"df: {len(groups) - 1}, {_n_total - len(groups)}")
print(f"N: {_n_total}")
for label, g in zip(group_labels, groups):
    print(f"  {label}: mean={g.mean():.4f}, n={len(g)}")
""",
    # Welch's ANOVA computed directly (no pingouin dependency) so it never
    # silently degrades to a regular ANOVA — which would defeat the whole point,
    # since Welch's is chosen precisely when variances are unequal.
    "welch_anova": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
grouped = [(label, g[__OUTCOME__].dropna()) for label, g in df.groupby(__GROUPING__)]
grouped = [(label, g) for label, g in grouped if len(g) > 1]
k = len(grouped)
n_i = np.array([len(g) for _, g in grouped])
mean_i = np.array([g.mean() for _, g in grouped])
var_i = np.array([g.var(ddof=1) for _, g in grouped])
w_i = n_i / var_i
w_sum = w_i.sum()
grand = (w_i * mean_i).sum() / w_sum
numerator = ((w_i * (mean_i - grand) ** 2).sum()) / (k - 1)
denom_term = (((1 - w_i / w_sum) ** 2) / (n_i - 1)).sum()
denominator = 1 + (2 * (k - 2) / (k ** 2 - 1)) * denom_term
F = numerator / denominator
df1 = k - 1
df2 = (k ** 2 - 1) / (3 * denom_term)
p = stats.f.sf(F, df1, df2)
grand_mean = df[__OUTCOME__].mean()
ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for _, g in grouped)
ss_total = sum((df[__OUTCOME__].dropna() - grand_mean) ** 2)
eta_sq = ss_between / ss_total if ss_total else float('nan')
print(f"F-statistic: {F:.4f}")
print(f"P-value: {p:.4f}")
print(f"Eta-squared: {eta_sq:.4f}")
print(f"df: {df1}, {df2:.2f}")
print(f"N: {int(n_i.sum())}")
for label, g in grouped:
    print(f"  {label}: mean={g.mean():.4f}, n={len(g)}")
""",
}

# Which sentinel tokens each template consumes. Correlation / categorical tests
# take a symmetric pair (col_a, col_b); group comparisons take (outcome, grouping).
_PAIR_TESTS = {"pearson", "spearman", "chi_square", "fisher_exact"}


def get_code_template(template_key: str) -> str | None:
    return CODE_TEMPLATES.get(template_key)


def render_template(template_key: str, *, col_a: str, col_b: str) -> str | None:
    """Fill a deterministic test template with real column names, SAFELY.

    For pair tests (correlation / categorical), col_a and col_b map to
    __COL_A__/__COL_B__. For group comparisons, col_a is the numeric OUTCOME and
    col_b is the categorical GROUPING variable (the caller must order them that
    way — `select_test` already normalizes this). Names are inserted via repr()
    so a maliciously-named column can't break out of the string literal.
    """
    template = CODE_TEMPLATES.get(template_key)
    if template is None:
        return None
    a, b = repr(col_a), repr(col_b)
    return (
        template
        .replace("__COL_A__", a)
        .replace("__COL_B__", b)
        .replace("__OUTCOME__", a)
        .replace("__GROUPING__", b)
    )


# ── Post-hoc pairwise comparisons (which groups differ after a significant
#    3+-group omnibus test) ──────────────────────────────────────────────────
# Maps the registry `posthoc` name to a pairwise method. Tukey HSD is the real
# thing (scipy); the Welch/Mann-Whitney variants are Holm-Bonferroni-corrected
# pairwise tests — dependency-safe, standard alternatives to Games-Howell/Dunn.
_POSTHOC_METHOD = {"tukey": "tukey", "games_howell": "welch", "dunn_bonferroni": "mannwhitney"}

_POSTHOC_LABEL = {
    "tukey": "Tukey HSD",
    "games_howell": "pairwise Welch t-tests (Holm-corrected)",
    "dunn_bonferroni": "pairwise Mann-Whitney tests (Holm-corrected)",
}

_POSTHOC_TEMPLATE = """
import pandas as pd, numpy as np
from scipy import stats
from itertools import combinations
df = pd.read_csv('/home/user/data.csv')
grouped = {str(label): g[__OUTCOME__].dropna().values for label, g in df.groupby(__GROUPING__)}
labels = [l for l in grouped if len(grouped[l]) > 1]
method = __METHOD__
print("=== POSTHOC ===")
done = False
if method == "tukey":
    try:
        from scipy.stats import tukey_hsd
        res = tukey_hsd(*[grouped[l] for l in labels])
        for i, j in combinations(range(len(labels)), 2):
            p = float(res.pvalue[i, j])
            print(f"{labels[i]} vs {labels[j]}: p_adj={p:.4f}, significant={'yes' if p < 0.05 else 'no'}")
        done = True
    except Exception:
        method = "student"  # fall back to pairwise t + Holm
if not done:
    pairs = list(combinations(labels, 2))
    ps = []
    for x, y in pairs:
        gx, gy = grouped[x], grouped[y]
        if method == "welch":
            _, p = stats.ttest_ind(gx, gy, equal_var=False)
        elif method == "mannwhitney":
            _, p = stats.mannwhitneyu(gx, gy, alternative="two-sided")
        else:
            _, p = stats.ttest_ind(gx, gy, equal_var=True)
        ps.append(float(p))
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    run = 0.0
    for rank, idx in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[idx]))
        adj[idx] = run
    for (x, y), pa in zip(pairs, adj):
        print(f"{x} vs {y}: p_adj={pa:.4f}, significant={'yes' if pa < 0.05 else 'no'}")
"""


def posthoc_label(posthoc_key: str) -> str:
    return _POSTHOC_LABEL.get(posthoc_key, "pairwise comparisons")


def render_posthoc(posthoc_key: str, outcome: str, grouping: str) -> str | None:
    """Fill the post-hoc template for a given omnibus test's posthoc method.
    outcome = the numeric column, grouping = the categorical column."""
    method = _POSTHOC_METHOD.get(posthoc_key)
    if method is None:
        return None
    return (
        _POSTHOC_TEMPLATE
        .replace("__OUTCOME__", repr(outcome))
        .replace("__GROUPING__", repr(grouping))
        .replace("__METHOD__", repr(method))
    )
