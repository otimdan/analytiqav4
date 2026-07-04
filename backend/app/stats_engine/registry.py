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


CODE_TEMPLATES: dict[str, str] = {
    "pearson": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
x = df['{var_a}'].dropna()
y = df['{var_b}'].dropna()
common = x.index.intersection(y.index)
x, y = x[common], y[common]
r, p = stats.pearsonr(x, y)
print(f"Pearson r: {r:.4f}")
print(f"P-value: {p:.4f}")
print(f"N: {len(x)}")
""",
    "spearman": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
x = df['{var_a}'].dropna()
y = df['{var_b}'].dropna()
common = x.index.intersection(y.index)
x, y = x[common], y[common]
rho, p = stats.spearmanr(x, y)
print(f"Spearman rho: {rho:.4f}")
print(f"P-value: {p:.4f}")
print(f"N: {len(x)}")
""",
    "independent_t": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = df['{grouping_var}'].dropna().unique()
g1 = df[df['{grouping_var}'] == groups[0]]['{outcome_var}'].dropna()
g2 = df[df['{grouping_var}'] == groups[1]]['{outcome_var}'].dropna()
t, p = stats.ttest_ind(g1, g2, equal_var=True)
pooled_std = np.sqrt(((len(g1)-1)*g1.std()**2 + (len(g2)-1)*g2.std()**2) / (len(g1)+len(g2)-2))
d = (g1.mean() - g2.mean()) / pooled_std
print(f"Group 1 ({groups[0]}): mean={g1.mean():.4f}, n={len(g1)}")
print(f"Group 2 ({groups[1]}): mean={g2.mean():.4f}, n={len(g2)}")
print(f"T-statistic: {t:.4f}")
print(f"P-value: {p:.4f}")
print(f"Cohen's d: {d:.4f}")
""",
    "mann_whitney": """
import pandas as pd
import numpy as np
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = df['{grouping_var}'].dropna().unique()
g1 = df[df['{grouping_var}'] == groups[0]]['{outcome_var}'].dropna()
g2 = df[df['{grouping_var}'] == groups[1]]['{outcome_var}'].dropna()
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
groups = [group['{outcome_var}'].dropna() for _, group in df.groupby('{grouping_var}')]
group_labels = df['{grouping_var}'].dropna().unique()
h, p = stats.kruskal(*groups)
n = sum(len(g) for g in groups)
epsilon_sq = (h - len(groups) + 1) / (n - len(groups))
print(f"H-statistic: {h:.4f}")
print(f"P-value: {p:.4f}")
print(f"Epsilon-squared: {epsilon_sq:.4f}")
for label, g in zip(group_labels, groups):
    print(f"  {label}: median={g.median():.4f}, n={len(g)}")
""",
    "chi_square": """
import pandas as pd
from scipy import stats
import numpy as np
df = pd.read_csv('/home/user/data.csv')
contingency = pd.crosstab(df['{var_a}'], df['{var_b}'])
chi2, p, dof, expected = stats.chi2_contingency(contingency)
n = contingency.values.sum()
cramers_v = np.sqrt(chi2 / (n * (min(contingency.shape) - 1)))
print(f"Chi-square statistic: {chi2:.4f}")
print(f"P-value: {p:.4f}")
print(f"Degrees of freedom: {dof}")
print(f"Cramer's V: {cramers_v:.4f}")
""",
    "fisher_exact": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
contingency = pd.crosstab(df['{var_a}'], df['{var_b}'])
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
groups = [group['{outcome_var}'].dropna() for _, group in df.groupby('{grouping_var}')]
group_labels = df['{grouping_var}'].dropna().unique()
f, p = stats.f_oneway(*groups)
grand_mean = df['{outcome_var}'].mean()
ss_between = sum(len(g) * (g.mean() - grand_mean)**2 for g in groups)
ss_total = sum((df['{outcome_var}'].dropna() - grand_mean)**2)
eta_sq = ss_between / ss_total
print(f"F-statistic: {f:.4f}")
print(f"P-value: {p:.4f}")
print(f"Eta-squared: {eta_sq:.4f}")
for label, g in zip(group_labels, groups):
    print(f"  {label}: mean={g.mean():.4f}, n={len(g)}")
""",
    "welch_anova": """
import pandas as pd
from scipy import stats
df = pd.read_csv('/home/user/data.csv')
groups = [group['{outcome_var}'].dropna() for _, group in df.groupby('{grouping_var}')]
group_labels = df['{grouping_var}'].dropna().unique()
try:
    import pingouin as pg
    result = pg.welch_anova(data=df, dv='{outcome_var}', between='{grouping_var}')
    print(result[['Source','F','p-unc','np2']].to_string())
except ImportError:
    f, p = stats.f_oneway(*groups)
    print(f"F-statistic (approx): {f:.4f}")
    print(f"P-value: {p:.4f}")
for label, g in zip(group_labels, groups):
    print(f"  {label}: mean={g.mean():.4f}, n={len(g)}")
""",
}


def get_code_template(template_key: str) -> str | None:
    return CODE_TEMPLATES.get(template_key)
