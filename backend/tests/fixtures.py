"""Known-answer datasets for the golden suite.

Each builder returns a DataFrame engineered so the assumption checks produce an
UNAMBIGUOUS outcome (strong signals + fixed seeds), so the correct test is
deterministic. Column names are chosen to avoid tripping the profiler's
semantic heuristics unless that's the point of the fixture.
"""
import numpy as np
import pandas as pd

SEED = 20260718


def _rng(offset=0):
    return np.random.default_rng(SEED + offset)


# ── numeric × numeric (correlation) ──────────────────────────────────────────
def two_numeric_normal() -> pd.DataFrame:
    r = _rng(1)
    height = r.normal(170, 10, 90)
    weight = 0.5 * height + r.normal(0, 5, 90)  # correlated, both ~normal
    return pd.DataFrame({"height": np.round(height, 1), "weight": np.round(weight, 1)})


def two_numeric_skewed() -> pd.DataFrame:
    r = _rng(2)
    height = r.normal(170, 10, 90)
    income = r.lognormal(9, 1.0, 90)  # heavily right-skewed
    return pd.DataFrame({"height": np.round(height, 1), "income": np.round(income, 1)})


def ordinal_and_numeric() -> pd.DataFrame:
    r = _rng(3)
    satisfaction_score = r.integers(1, 6, 90)  # 'score' -> ordinal
    height = r.normal(170, 10, 90)
    return pd.DataFrame({"satisfaction_score": satisfaction_score, "height": np.round(height, 1)})


# ── numeric × categorical (group comparison) ─────────────────────────────────
def _two_group(sd_a, sd_b, dist="normal", n=50):
    r = _rng(4)
    arm = np.array(["control"] * n + ["treatment"] * n)
    if dist == "normal":
        a = r.normal(100, sd_a, n)
        b = r.normal(108, sd_b, n)
    else:  # skewed
        a = r.exponential(20, n) + 60
        b = r.exponential(30, n) + 60
    bp = np.concatenate([a, b])
    return pd.DataFrame({"bp": np.round(bp, 1), "arm": arm})


def numeric_by_2group_equalvar():
    return _two_group(12, 12, "normal")


def numeric_by_2group_unequalvar():
    return _two_group(6, 28, "normal")  # very different spreads -> Levene fails


def numeric_by_2group_skewed():
    return _two_group(0, 0, "skewed")


def _three_group(sds, dist="normal", n=45):
    r = _rng(5)
    grp = np.array(["north"] * n + ["south"] * n + ["east"] * n)
    if dist == "normal":
        parts = [r.normal(m, s, n) for m, s in zip((100, 106, 112), sds)]
    else:
        parts = [r.exponential(sc, n) + 50 for sc in (15, 22, 30)]
    bp = np.concatenate(parts)
    return pd.DataFrame({"bp": np.round(bp, 1), "region": grp})


def numeric_by_3group_equalvar():
    return _three_group((12, 12, 12), "normal")


def numeric_by_3group_unequalvar():
    return _three_group((5, 15, 30), "normal")


def numeric_by_3group_skewed():
    return _three_group((0, 0, 0), "skewed")


# ── categorical × categorical ────────────────────────────────────────────────
def two_categorical_2x2_adequate() -> pd.DataFrame:
    r = _rng(6)
    n = 200
    sex = r.choice(["M", "F"], n)
    # associate outcome with sex so it's a real signal, adequate cell counts
    passed = np.where(r.random(n) < np.where(sex == "M", 0.4, 0.65), "yes", "no")
    return pd.DataFrame({"sex": sex, "passed": passed})


def two_categorical_2x2_small() -> pd.DataFrame:
    r = _rng(7)
    n = 16  # tiny -> expected cell counts < 5
    sex = r.choice(["M", "F"], n)
    passed = r.choice(["yes", "no"], n)
    return pd.DataFrame({"sex": sex, "passed": passed})


def two_categorical_3x3_small() -> pd.DataFrame:
    r = _rng(8)
    n = 27  # 3x3 with small cells -> chi-square (Fisher template is 2x2 only)
    region = r.choice(["north", "south", "east"], n)
    grade = r.choice(["low", "mid", "high"], n)
    return pd.DataFrame({"region": region, "grade": grade})


# ── classification fixtures ──────────────────────────────────────────────────
def classification_dataset() -> pd.DataFrame:
    r = _rng(9)
    n = 120
    return pd.DataFrame({
        "patient_weight": np.round(r.uniform(50, 95, n), 1),     # float measurement -> NUMERIC
        "age": r.integers(18, 80, n),                            # int measurement  -> NUMERIC
        "satisfaction_score": r.integers(1, 6, n),               # 'score'          -> NUMERIC_OR_ORDINAL
        "sex": r.choice(["M", "F"], n),                          # text             -> CATEGORICAL
        "arm": r.choice([0, 1], n),                              # int 2-level      -> CATEGORICAL
        "session_time": r.choice(["morning", "evening"], n),     # 'time' but text  -> CATEGORICAL
        "patient_id": np.arange(1000, 1000 + n),                 # id name+unique   -> IDENTIFIER
        "email": [f"user{i}@x.com" for i in range(n)],           # unique strings   -> IDENTIFIER
        "visit_date": pd.date_range("2025-01-01", periods=n, freq="D").astype(str),  # DATETIME
    })
