# Analytika Roadmap → the go-to tool for research quantitative analysis

**Strategy in one line:** don't out-flexible Julius — *out-trust* it. Keep the
deterministic verified engine as the spine, extend it to the methods research
actually runs on, and win on **defensible, reproducible, publication-ready**
analysis. Keep the honest verified/assisted (unverified) boundary as a feature.

Do these **in order**. Goal 0 is foundational — it protects the verified
guarantee as every later goal adds surface.

---

## ⚙️ Goal 0 — Golden-test suite for the engine (foundational)
Lock in the currently-correct behavior before adding methods.
- Curated datasets with **known-correct** test choice + expected numbers
  (t-test, ANOVA, chi-square, correlations × normal / skewed / unequal-variance /
  small-n variants).
- Automated assertions: `profile → classify → resolve → assumption checks →
  select → run` yields the expected test + value (within tolerance).
- Runs locally/CI **without E2B** (execute the profiler/check/test scripts
  locally with scipy — same code, local execution).
- Pure-logic coverage too: Benjamini-Hochberg, fuzzy test-name matching, the
  assumption-aware override guard, variable classification.

## 📈 Goal 1 — Verified regression + multivariable models (highest leverage)
Research's center of gravity; currently only in the unverified tier.
- **Decide inference backend first:** proper regression needs SEs / p-values /
  CIs / VIF / diagnostics → statsmodels. Justify a custom E2B template that
  preinstalls it for the verified path (don't per-sandbox install).
- **Model spec capture:** outcome + predictors; dummy-code categoricals
  deterministically. Guided mode asks explicitly.
- **Regression assumption module:** linearity, multicollinearity (VIF),
  homoscedasticity (Breusch-Pagan), residual normality, independence
  (Durbin-Watson), influential points (Cook's distance).
- **Verified templates:** multiple linear regression, logistic regression, ANCOVA.
- **Selection logic:** linear vs logistic from outcome type; warnings.
- **Artifact + report shape:** coefficient table + diagnostics + verified badge.
- **Guided sub-flow:** specify model → assumption/diagnostics → fit → interpret.

## 🧹 Goal 2 — Real, tracked data cleaning
Defensible analysis starts with defensible data prep.
- **Cleaning operations registry** (like the test registry): deterministic
  transforms — missing-data handling, type coercion, recoding, outlier
  detection/handling, derived columns, filtering. LLM picks operation+params
  from a menu; engine executes deterministically.
- **Durable cleaned dataset:** persist as the new working data (fixes the
  replay-durability gap); re-profile. Wire the dormant `cleaned_dataset` artifact.
- **Audit log:** every transformation recorded, inspectable, reversible.
- **Quality surfacing:** missingness map, outlier flags, before/after.
- Becomes a real Guided stage 1.

## 📄 Goal 3 — Publication-grade output (the "go-to" converter)
- **Auto methods section** (APA/journal style) generated from stored artifact
  metadata ("Normality was assessed via Shapiro-Wilk…").
- **APA results reporting:** correct notation — `t(88)=2.34, p=.021, d=0.50`.
- **Formatted APA tables** + **export** (Word / PDF / LaTeX), copy-ready.
- **Reproducibility appendix:** exact tests, decisions, assumption results, versions.

---

## 🛡️ Cross-cutting — strengthen the system (runs in parallel, don't defer)

**Statistical trust (the moat — invest most):**
- Independent **statistician review** of the decision tree + thresholds
  (sample-size ≥20, skew/Shapiro cutoffs; the static path still uses the old CV
  variance heuristic — audit it).
- **Wire post-hoc tests** (Tukey / Dunn / Games-Howell named in the registry but
  not executed) — a significant ANOVA needs them.
- Effect sizes + **confidence intervals on every test**; power/sample-size warnings.

**Reliability & scale (blocks real launch):**
- **Drive the real browser UI** (Playwright / manual) — biggest untested surface.
- **Concurrency:** rate limiter is in-memory (needs Redis multi-instance);
  load-test sandbox management.
- **Deploy** (Vercel + backend host); runs locally only today.
- **Security review** of the branch; **observability** (Sentry + analytics).
- **Automated backend tests** (unit + integration) beyond the engine golden suite.

**Product/robustness:**
- Wide/large datasets (many columns; sampling for big files).
- More deterministic classifier routing (reduce LLM variance).
- **Live-test Dodo payments** end-to-end before charging.
