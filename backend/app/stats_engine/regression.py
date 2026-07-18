"""Deterministic verified regression (Goal 1).

Same philosophy as the bivariate engine: the model is RESOLVED deterministically
(outcome + predictors → linear vs logistic, which predictors are categorical),
then an AUDITED statsmodels template is executed DIRECTLY (no LLM code-gen). The
LLM only narrates the printed results. Diagnostics (VIF, homoscedasticity,
independence, residual normality) are computed alongside the fit and surfaced as
caveats — they don't silently switch the model.

Column names are attacker-controlled, so the templates reference columns only
via repr()'d literals / a repr()'d name list (never string-formatted into code),
and use the statsmodels ARRAY api (no formula-string parsing of names).
"""
from typing import Any, Optional

from app.stats_engine.variable_classifier import (
    classify_variable, is_suitable_for_analysis,
    NUMERIC, NUMERIC_OR_ORDINAL, CATEGORICAL,
)
from app.stats_engine.variable_classifier import get_group_count

_NUMERICISH = (NUMERIC, NUMERIC_OR_ORDINAL)


def resolve_model(outcome: str, predictors: list[str], profile: dict[str, Any]) -> dict[str, Any]:
    """Validate + type a regression spec and pick the model family. Returns either
    an error dict {ok: False, reason, ...} or {ok: True, model_type, outcome,
    predictors, categoricals, ...}."""
    if not outcome or not predictors:
        return _err("A regression needs an outcome and at least one predictor.")
    predictors = [p for p in dict.fromkeys(predictors) if p != outcome]  # dedupe, drop outcome
    if not predictors:
        return _err("A regression needs at least one predictor different from the outcome.")

    ok, reason = is_suitable_for_analysis(outcome, profile)
    if not ok:
        return _err(f"Outcome '{outcome}' can't be used: {reason}")
    for p in predictors:
        ok, reason = is_suitable_for_analysis(p, profile)
        if not ok:
            return _err(f"Predictor '{p}' can't be used: {reason}")

    outcome_type = classify_variable(outcome, profile)

    # Model family from the outcome type.
    if outcome_type in _NUMERICISH:
        model_type = "linear"
    elif outcome_type == CATEGORICAL and get_group_count(outcome, profile) == 2:
        model_type = "logistic"
    elif outcome_type == CATEGORICAL:
        return _err(
            f"'{outcome}' has more than two categories — multinomial/ordinal regression "
            f"isn't in the verified library yet. Pick a numeric outcome (linear) or a "
            f"binary one (logistic)."
        )
    else:
        return _err(f"'{outcome}' isn't a usable regression outcome.")

    categoricals = [p for p in predictors if classify_variable(p, profile) == CATEGORICAL]
    return {
        "ok": True, "model_type": model_type, "outcome": outcome,
        "predictors": predictors, "categoricals": categoricals,
    }


def _err(reason: str) -> dict[str, Any]:
    return {"ok": False, "reason": reason}


# ── Templates (executed directly; only the repr()'d names/lists are injected) ──

_LINEAR_TEMPLATE = '''
import pandas as pd, numpy as np
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson
from scipy import stats as sps

df = pd.read_csv('/home/user/data.csv')
outcome = __OUTCOME__
predictors = __PREDICTORS__
categoricals = __CATEGORICALS__

data = df[[outcome] + predictors].dropna()
y = data[outcome].astype(float)
parts = []
for p in predictors:
    if p in categoricals:
        parts.append(pd.get_dummies(data[p].astype(str), prefix=p, drop_first=True).astype(float))
    else:
        parts.append(data[[p]].astype(float))
X = sm.add_constant(pd.concat(parts, axis=1))
X.columns = [str(c) for c in X.columns]
model = sm.OLS(y, X).fit()

print("=== MODEL ===")
print(f"Model: Linear regression (OLS)")
print(f"Outcome: {outcome}")
print(f"N: {int(model.nobs)}")
print(f"R-squared: {model.rsquared:.4f}")
print(f"Adjusted R-squared: {model.rsquared_adj:.4f}")
print(f"F-statistic: {model.fvalue:.4f}")
print(f"P-value: {model.f_pvalue:.6f}")
print("=== COEFFICIENTS ===")
ci = model.conf_int()
for name in model.params.index:
    print(f"{name}: coef={model.params[name]:.4f}, se={model.bse[name]:.4f}, t={model.tvalues[name]:.4f}, p={model.pvalues[name]:.4f}, ci=[{ci.loc[name, 0]:.4f}, {ci.loc[name, 1]:.4f}]")
print("=== DIAGNOSTICS ===")
cols = [c for c in X.columns if c != "const"]
if len(cols) > 1:
    for c in cols:
        idx = list(X.columns).index(c)
        try:
            print(f"VIF {c}: {variance_inflation_factor(X.values, idx):.3f}")
        except Exception:
            pass
try:
    bp = het_breuschpagan(model.resid, X)
    print(f"Breusch-Pagan p (homoscedasticity): {bp[1]:.4f}")
except Exception:
    pass
print(f"Durbin-Watson (independence): {durbin_watson(model.resid):.4f}")
try:
    _, nlp = sps.normaltest(model.resid)
    print(f"Residual normality p: {nlp:.4f}")
except Exception:
    pass
'''

_LOGISTIC_TEMPLATE = '''
import pandas as pd, numpy as np
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

df = pd.read_csv('/home/user/data.csv')
outcome = __OUTCOME__
predictors = __PREDICTORS__
categoricals = __CATEGORICALS__

data = df[[outcome] + predictors].dropna()
levels = sorted(data[outcome].astype(str).unique())
y = (data[outcome].astype(str) == levels[-1]).astype(float)  # model P(outcome == last level)
parts = []
for p in predictors:
    if p in categoricals:
        parts.append(pd.get_dummies(data[p].astype(str), prefix=p, drop_first=True).astype(float))
    else:
        parts.append(data[[p]].astype(float))
X = sm.add_constant(pd.concat(parts, axis=1))
X.columns = [str(c) for c in X.columns]
model = sm.Logit(y, X).fit(disp=0)

print("=== MODEL ===")
print(f"Model: Logistic regression")
print(f"Outcome: {outcome} (modelling P({outcome} = {levels[-1]}))")
print(f"N: {int(model.nobs)}")
print(f"Pseudo R-squared: {model.prsquared:.4f}")
print(f"LLR P-value: {model.llr_pvalue:.6f}")
print("=== COEFFICIENTS ===")
ci = model.conf_int()
for name in model.params.index:
    print(f"{name}: coef={model.params[name]:.4f}, se={model.bse[name]:.4f}, z={model.tvalues[name]:.4f}, p={model.pvalues[name]:.4f}, or={np.exp(model.params[name]):.4f}, ci=[{ci.loc[name, 0]:.4f}, {ci.loc[name, 1]:.4f}]")
print("=== DIAGNOSTICS ===")
cols = [c for c in X.columns if c != "const"]
if len(cols) > 1:
    for c in cols:
        idx = list(X.columns).index(c)
        try:
            print(f"VIF {c}: {variance_inflation_factor(X.values, idx):.3f}")
        except Exception:
            pass
'''

_TEMPLATES = {"linear": _LINEAR_TEMPLATE, "logistic": _LOGISTIC_TEMPLATE}


def render_regression(model_type: str, outcome: str, predictors: list[str], categoricals: list[str]) -> Optional[str]:
    """Fill a regression template with repr()'d names/lists (injection-safe)."""
    template = _TEMPLATES.get(model_type)
    if template is None:
        return None
    return (
        template
        .replace("__OUTCOME__", repr(outcome))
        .replace("__PREDICTORS__", repr(list(predictors)))
        .replace("__CATEGORICALS__", repr(list(categoricals)))
    )
