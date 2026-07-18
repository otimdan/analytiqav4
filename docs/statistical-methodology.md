# Statistical Methodology — Review Document

**Purpose:** give an independent statistician everything needed to audit *how this
tool chooses and runs a statistical test*, without reading the source. Every rule,
threshold, and formula below is transcribed directly from the production code
(`backend/app/stats_engine/`), with file references so you can spot-check.

**What we are asking you to certify:** that the decision tree, thresholds, and
assumption procedures are *statistically defensible* for the audience (applied
researchers running standard bivariate tests + regression), and to flag anything
you would change. A prioritized list of the specific judgment calls we most want
your ruling on is in **§9 (Questions for the reviewer)** — start there if you're
short on time.

**Scope of this document:** the *verified* engine only — the deterministic path
that selects and runs a test from a fixed library. A separate "assisted" tier
(LLM-written code for combinations the library doesn't cover) is explicitly
labelled as unverified in the product and is **out of scope** for this review.

**Version:** describes `main` @ commit `593d603` (2026-07-19).

---

## 1. Design philosophy (why this is auditable at all)

The core claim of the product is *trust through determinism*: for any supported
analysis, the test is selected by a fixed decision tree and executed by a
**pre-written, audited code template** — never by LLM-generated code. The number
the user sees is always SciPy's number for a known procedure. An LLM is used only
to (a) parse the user's request into columns/intent and (b) write a plain-language
narration *after* the fact; it never picks the test or computes the statistic.

Consequently the entire selection logic is a pure function of the data + fixed
thresholds, and is locked by a golden-test suite (198 tests) that runs the real
code on known-answer datasets. §10 lists worked examples from that suite.

## 2. The pipeline

For a request naming two columns, the engine runs:

```
profile(dataset)          → per-column descriptive stats + type heuristics   (§3)
classify(each column)     → numeric / ordinal / categorical / id / ...       (§3)
resolve_pair(a, b)        → validate, order (numeric outcome first), count groups
run_live_checks(a, b)     → assumption tests on the CURRENT data, in-sandbox  (§4)
decide_test(resolved,     → walk the decision tree to one recommended test    (§5)
            checks)
execute(template)         → run the audited SciPy template, parse the numbers (§6–7)
```

`resolve_pair`/`decide_test` are in `stats_engine/test_selector.py`; the live
checks are in `stats_engine/assumption_checks.py`; templates in
`stats_engine/registry.py`.

> **Two assumption-check implementations exist; only one is used in production.**
> The production `confirmatory` regime uses the **live** checks in §4 (real tests
> on the live data, in the sandbox). A second, profile-only path (`select_test` →
> `run_all_checks`, which uses a coefficient-of-variation heuristic for variance
> and a skewness cutoff for normality) exists in the code but is **not called by
> any production route** — it is a leftover convenience used only by unit tests.
> We flag it in §9(h) as a candidate for removal. **Everything in §4 is the live,
> production behaviour.**

## 3. Variable classification

Each column is assigned one type. Analysis proceeds only for
`numeric`, `numeric_or_ordinal`, and `categorical`; `identifier`, `free_text`,
`datetime`, and `unknown` are rejected with a message
(`variable_classifier.py::is_suitable_for_analysis`). A column >80% missing is
also rejected.

Classification order (`variable_classifier.py::classify_variable`), first match wins:

| # | Rule | Result |
|---|------|--------|
| 1 | Values parse as dates (>80% non-null after `to_datetime`) | `datetime` (rejected) |
| 2 | Float dtype | `numeric` (or `numeric_or_ordinal` if the name implies a scale) |
| 3 | Integer dtype **and** an ordinal-scale name (score/rating/grade/level/severity/stage/rank) | `numeric_or_ordinal` |
| 4 | Name looks like an id, **or** non-numeric with uniqueness ratio > 0.95 | `identifier` (rejected) |
| 5 | Free-text name (name/comment/notes/description/address/reason) | `free_text` (rejected) |
| 6 | Integer with ≤10 distinct values, **or** any string/categorical dtype, **or** a grouping name (group/arm/treatment/sex/region/…) | `categorical` |
| 7 | Any remaining numeric | `numeric` |

The name-keyword heuristics feed a `semantic_guess` computed in the profiler
(`profiling/profiler.py`). **Key structural thresholds:**
- **Integer with ≤ 10 unique values → treated as categorical** (a grouping code).
- **Non-numeric with > 95% unique values → identifier** (names/emails/codes).
- Numeric floats are *never* reclassified as identifiers by uniqueness (continuous
  data is expected to be highly unique).

Ordinal (Likert-type) integers keep their ordering and are routed to rank-based
tests (Spearman / non-parametric), never to a nominal test.

## 4. Assumption checks (live, production path)

Run in-sandbox on the current data (`assumption_checks.py::_build_check_script`).
Each returns `pass` / `fail` / `not_applicable`. The vocabulary and keys are shared
with the decision tree.

**Normality** — `_normal(series)`:
- n < 3 or fewer than 3 distinct values → `not_applicable`.
- **n ≥ 20:** D'Agostino–Pearson omnibus test (`scipy.stats.normaltest`).
- **n < 20:** Shapiro–Wilk (`scipy.stats.shapiro`).
- **Decision: `pass` iff p ≥ 0.01** (deliberately α = .01, not .05 — see §9a).
- For a **numeric × categorical** comparison, normality is assessed **once**, on
  the pooled, **group-standardized residuals** `concat((xᵢ − mean_g)/sd_g)` across
  groups — i.e. the within-group residual distribution the parametric test
  actually assumes — rather than testing each group separately or the raw pooled
  column. (Rationale: one test avoids multiplicity; standardizing decouples
  normality from unequal variance.) See §9b.
- For a **numeric × numeric** pair, each variable is tested separately.

**Homogeneity of variance** — numeric × categorical only:
- **Levene's test, median-centered** (i.e. Brown–Forsythe), `scipy.stats.levene(..., center='median')`.
- **Decision: `pass` iff p ≥ 0.05.**

**Adequate sample size** — `sample_size_ok`:
- numeric × categorical: `pass` iff the **smallest group** has ≥ **20** rows.
- numeric × numeric / categorical × categorical: `pass` iff total complete rows ≥ 20.
- Threshold `MIN_SAMPLE_SIZE_PER_GROUP = 20` (`config.py`). See §9c.

**Minimum expected cell count** — categorical × categorical only:
- Build the contingency table; `pass` iff the **minimum expected count ≥ 5**
  (`scipy.stats.chi2_contingency` expected matrix). Threshold
  `CHI_SQUARE_MIN_EXPECTED_CELL = 5` (`config.py`).

## 5. Test-selection decision tree

`test_selector.py::decide_test`, branching on the resolved pair's types. Each leaf
names the recommended test and ordered alternates.

**A. numeric × numeric** (`_correlation_branch`)
- Both variables `pass` normality **and both are strictly `numeric`** (neither is
  ordinal) → **Pearson** *r*.
- Otherwise (either non-normal, or either is ordinal) → **Spearman** ρ.

**B. numeric × categorical, exactly 2 groups** (`_two_group_branch`)
- normality `fail` **OR** sample-size `fail` → **Mann–Whitney U**.
- else variance `fail` → **Welch's t-test**.
- else → **Independent-samples t-test** (Student).

**C. numeric × categorical, ≥ 3 groups** (`_multi_group_branch`)
- normality `fail` **OR** sample-size `fail` → **Kruskal–Wallis** (+ Dunn post-hoc).
- else variance `fail` → **Welch's ANOVA** (+ Games–Howell-style post-hoc).
- else → **One-way ANOVA** (+ Tukey HSD post-hoc).

**D. categorical × categorical** (`_categorical_branch`)
- expected-cell `fail` **and** table is 2×2 → **Fisher's exact test**.
- expected-cell `fail` **and** table larger than 2×2 → **chi-square, with an
  explicit caveat** in the output (Fisher's template is 2×2-only; an exact test
  would be preferable but isn't available for larger tables). See §9g.
- else → **Pearson chi-square test of independence**.

Note the precedence in B and C: **normality/sample-size failure takes priority
over the variance branch** — a small or non-normal sample goes non-parametric
regardless of the variance result. See §9d.

### Honoring explicit user requests (override guard)
If the user names a specific test, the engine will run it **unless doing so would
re-introduce a violated assumption** (`confirmatory.py::_is_assumption_downgrade`):
it refuses to downgrade a non-parametric recommendation to a parametric one, or a
variance-robust choice (Welch) to its equal-variance counterpart, when the checks
failed. It *will* honor a request that moves to a more conservative test.

## 6. Effect sizes (as implemented)

Computed inside the same audited templates (`registry.py`):

| Test | Effect size | Formula as coded |
|------|-------------|------------------|
| Independent t / Welch t | Cohen's *d* | (mean₁ − mean₂) / *s_pooled*, with *s_pooled* = √[((n₁−1)s₁² + (n₂−1)s₂²)/(n₁+n₂−2)] — **pooled SD used even for Welch** (§9e) |
| Mann–Whitney | rank-biserial *r* | 1 − 2U/(n₁n₂) |
| One-way ANOVA | η² | SS_between / SS_total |
| Welch's ANOVA | η² | SS_between / SS_total (unweighted; not an ω²/Welch-weighted variant) (§9f) |
| Kruskal–Wallis | ε² | (H − k + 1)/(n − k) |
| Chi-square | Cramér's *V* | √(χ²/(n·(min(r,c)−1))) |
| Fisher's exact | odds ratio | `scipy.stats.fisher_exact` |
| Pearson / Spearman | *r* / ρ | the coefficient itself |

Degrees of freedom are computed and reported for APA output: t = n₁+n₂−2 (Student)
or Welch–Satterthwaite (Welch); ANOVA (k−1, N−k); correlation N−2; χ² from the
table; Kruskal k−1.

**Chi-square continuity correction:** `chi2_contingency` is called with SciPy's
default `correction=True`, so **Yates' continuity correction is applied to 2×2
tables** (not to larger tables). Flag if you'd prefer it off (§9g).

## 7. Multiple comparisons & post-hoc

**Family-wise correction (report level).** When a session contains more than one
*verified* test with a p-value, the report applies a **Benjamini–Hochberg FDR**
correction across them and only calls a result significant at the **adjusted** p.
Assisted (unverified) analyses are listed separately and are **not** pooled into
the correction. See §9i on the family definition.

**Post-hoc (which groups differ), auto-run only when the omnibus test is
significant** (`registry.py`):
- One-way ANOVA → **Tukey HSD** (`scipy.stats.tukey_hsd`).
- Welch's ANOVA → pairwise **Welch t-tests, Holm-corrected** (a dependency-safe
  stand-in for Games–Howell).
- Kruskal–Wallis → pairwise **Mann–Whitney tests, Holm-corrected** (a stand-in for
  Dunn's test).

See §9j on whether the Holm-corrected pairwise substitutes are acceptable.

## 8. Regression (verified)

`stats_engine/regression.py`, executed via audited statsmodels templates.
- **Model family from outcome type:** numeric outcome → **OLS linear**; binary
  categorical outcome → **logistic**; a >2-level categorical outcome is refused
  (multinomial/ordinal not in the verified library).
- Categorical predictors are dummy-coded (drop-first) deterministically.
- **Reported:** coefficients with SE, t/z, p, 95% CI; R²/adj-R² (linear) or
  McFadden pseudo-R² + odds ratios (logistic); overall F (linear).
- **Diagnostics computed alongside** (surfaced as caveats, never silently
  switching the model): VIF (multicollinearity), Breusch–Pagan
  (heteroscedasticity), Durbin–Watson (independence), residual normality
  (`normaltest`). Cook's distance / influence is **not yet** computed (§9k).

## 9. Questions for the reviewer (the judgment calls)

These are the specific decisions where we most want your ruling. Each is a place
the code makes a defensible-but-arguable choice.

**(a) Normality pre-test at α = .01.** We reject normality only on strong evidence
(p < .01), reasoning that normality tests over-reject at n up in the hundreds and
that t/ANOVA are robust to mild non-normality. Is α = .01 the right operating
point, or should it scale with n (or be dropped in favour of a skew/kurtosis rule
or an assumption-free default)?

**(b) Testing pooled group-standardized residuals for normality.** For group
comparisons we run a single normality test on the standardized within-group
residuals rather than per group. Do you agree this is the right target, and is a
single omnibus test on the pooled residuals preferable to per-group testing?

**(c) Small-sample cutoff n < 20 per group → non-parametric.** Is 20 the right
threshold? (Common alternatives: ~30 for CLT comfort, or no hard cutoff.)

**(d) Precedence: non-normal/small ⇒ non-parametric before checking variance.** In
the 2-/3+-group branches, a normality or sample failure routes to
Mann–Whitney/Kruskal *regardless of variance*. Is collapsing "small sample" and
"non-normal" into the same non-parametric branch appropriate, or should small-but-
normal samples still use a (Welch) parametric test?

**(e) Cohen's d with pooled SD under unequal variance (Welch).** We report Cohen's
*d* with a pooled SD even when Welch's t was chosen for unequal variances. Would
you prefer Glass's Δ, a non-pooled standardizer, or Hedges' g (small-sample
correction) here?

**(f) η² for Welch's ANOVA.** We report an unweighted η² (SS-based) alongside
Welch's ANOVA. Should this be ω² or a Welch-consistent effect size instead?

**(g) Chi-square: Yates on 2×2, and chi-square-with-caveat for large sparse
tables.** Two sub-questions: (i) keep SciPy's default Yates correction on 2×2? (ii)
for a >2×2 table with small expected counts we currently run chi-square with a
printed caveat (no exact test available for large tables) — acceptable, or should
we refuse / do something else?

**(h) Default to Welch, or Student when variances look equal?** Some argue Welch's
t/ANOVA should be the *default* regardless of the variance test (which is itself
underpowered). We currently use Student/one-way ANOVA when variance passes. Change
the default?

**(i) FDR family = "all verified tests in a session."** Is session-level pooling
the right family definition for the Benjamini–Hochberg correction, given a session
may mix tests on unrelated variables? Should the family be narrower (per research
question) or should correction be opt-in?

**(j) Post-hoc substitutes.** Holm-corrected pairwise Welch (for Games–Howell) and
Holm-corrected pairwise Mann–Whitney (for Dunn). Acceptable stand-ins, or should we
add the exact procedures?

**(k) Regression diagnostics.** We report VIF, Breusch–Pagan, Durbin–Watson, and
residual normality, but not Cook's distance / leverage. Is that an acceptable
starting set, and are the diagnostic thresholds we flag on (VIF > 5, BP/normality
p < .05) the ones you'd use?

## 10. Worked examples (locked by the golden suite)

Each row is a known-answer dataset from `backend/tests/fixtures.py`; the engine is
regression-tested to select exactly this test on exactly this data. These are the
best concrete cases to sanity-check the tree against your own judgement.

| Dataset (fixture) | Shape | Live checks | Selected test | Why |
|---|---|---|---|---|
| `two_numeric_normal` (height, weight) | numeric × numeric, both ~normal | both normality pass | **Pearson** | both numeric & normal |
| `two_numeric_skewed` (height, income) | numeric × numeric, income lognormal | normality fail | **Spearman** | non-normal |
| `numeric_by_2group_equalvar` (bp, arm) | 2 groups, normal, equal var | norm pass, var pass | **Independent t** | all parametric assumptions met |
| `numeric_by_2group_unequalvar` (bp, arm) | 2 groups, normal, unequal var | norm pass, var **fail** | **Welch's t** | variance heterogeneity |
| `numeric_by_2group_skewed` (bp, arm) | 2 groups, exponential | norm **fail** | **Mann–Whitney** | non-normal |
| `numeric_by_3group_equalvar` (bp, region) | 3 groups, normal, equal var | norm pass, var pass | **One-way ANOVA** (+ Tukey) | parametric, 3 groups |
| `numeric_by_3group_unequalvar` (bp, region) | 3 groups, unequal var | norm pass, var **fail** | **Welch's ANOVA** (+ Games–Howell-style) | variance heterogeneity |
| `numeric_by_3group_skewed` (bp, region) | 3 groups, exponential | norm **fail** | **Kruskal–Wallis** (+ Dunn-style) | non-normal |
| `two_categorical_2x2_adequate` (sex, passed) | 2×2, n=200 | expected cells pass | **Chi-square** | adequate cell counts |
| `two_categorical_2x2_small` (sex, passed) | 2×2, n=16 | expected cells **fail** | **Fisher's exact** | small expected counts, 2×2 |
| `two_categorical_3x3_small` (region, grade) | 3×3, n=27 | expected cells **fail** | **Chi-square (caveated)** | small counts but Fisher template is 2×2-only |

To reproduce any of these locally (no sandbox, no API keys):
`cd backend && pytest tests/test_engine_golden.py -v`.

## 11. Test registry (the full verified library)

`stats_engine/registry.py`. Anything outside this list falls to the unlabeled
assisted tier (out of scope here).

| Test | Category | Requires | Effect size | Post-hoc |
|------|----------|----------|-------------|----------|
| Pearson correlation | correlation | numeric × numeric | *r* | — |
| Spearman correlation | correlation | numeric/ordinal × numeric/ordinal | ρ | — |
| Independent-samples t | group comparison (2) | numeric × categorical | Cohen's *d* | — |
| Welch's t | group comparison (2) | numeric × categorical | Cohen's *d* | — |
| Mann–Whitney U | group comparison (2) | numeric/ordinal × categorical | rank-biserial *r* | — |
| One-way ANOVA | group comparison (3+) | numeric × categorical | η² | Tukey HSD |
| Welch's ANOVA | group comparison (3+) | numeric × categorical | η² | Games–Howell-style |
| Kruskal–Wallis | group comparison (3+) | numeric/ordinal × categorical | ε² | Dunn-style |
| Chi-square | categorical association | categorical × categorical | Cramér's *V* | — |
| Fisher's exact | categorical association | categorical × categorical (2×2) | odds ratio | — |
| Linear regression (OLS) | regression | numeric outcome + predictors | R² | diagnostics |
| Logistic regression | regression | binary outcome + predictors | pseudo-R², OR | diagnostics |

---

*Prepared for external statistical review. Please annotate directly, focusing on
§9. Source of truth: `backend/app/stats_engine/` at commit `593d603`.*
