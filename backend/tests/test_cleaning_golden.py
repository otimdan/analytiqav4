"""Golden tests for deterministic cleaning operations (Goal 2). Runs the REAL
transform templates locally, reads back the rewritten CSV, and checks the
transform + audit summary. No E2B, no network."""
import os
import json
import pandas as pd
import pytest

from tests import fixtures as F
from tests._local_sandbox import write_csv, run_script
from app.cleaning.operations import render_operation, resolve_operation, OPERATIONS


def run_cleaning(df, op, params):
    code = render_operation(op, params)
    path = write_csv(df)
    try:
        out = run_script(code, path)
        summary = json.loads(out.strip().splitlines()[-1])
        return summary, pd.read_csv(path)
    finally:
        os.remove(path)


class TestOperations:
    def test_coerce_numeric_strips_currency(self):
        summary, df = run_cleaning(F.messy_dataset(), "coerce_numeric", {"column": "price"})
        assert pd.api.types.is_numeric_dtype(df["price"])
        assert df["price"].dropna().tolist() == [1200.0, 980.0, 1050.0, 2000.0]

    def test_impute_missing_median(self):
        summary, df = run_cleaning(F.messy_dataset(), "impute_missing", {"column": "age", "strategy": "median"})
        assert df["age"].isna().sum() == 0
        assert summary["filled"] == 1

    def test_impute_missing_constant(self):
        summary, df = run_cleaning(F.messy_dataset(), "impute_missing", {"column": "age", "strategy": "constant", "value": 0})
        assert df["age"].isna().sum() == 0

    def test_drop_missing_all(self):
        summary, df = run_cleaning(F.messy_dataset(), "drop_missing", {"columns": None})
        assert df.isna().sum().sum() == 0
        assert summary["removed"] == summary["rows_before"] - summary["rows_after"]

    def test_drop_missing_subset(self):
        summary, df = run_cleaning(F.messy_dataset(), "drop_missing", {"columns": ["age"]})
        assert df["age"].isna().sum() == 0  # only age's missing row dropped

    def test_remove_outliers_iqr(self):
        summary, df = run_cleaning(F.messy_dataset(), "remove_outliers", {"column": "age", "method": "iqr", "action": "remove"})
        assert 200 not in df["age"].dropna().tolist()
        assert summary["affected"] == 1

    def test_cap_outliers(self):
        summary, df = run_cleaning(F.messy_dataset(), "remove_outliers", {"column": "age", "method": "iqr", "action": "cap"})
        assert df["age"].dropna().max() < 200  # capped to the upper bound

    def test_recode_merges_categories(self):
        summary, df = run_cleaning(F.messy_dataset(), "recode", {"column": "region", "mapping": {"north": "North", "SOUTH": "South"}})
        assert set(df["region"].unique()) == {"North", "South"}

    def test_filter_rows_gt(self):
        summary, df = run_cleaning(F.messy_dataset(), "filter_rows", {"column": "score", "operator": ">", "value": 25})
        assert df["score"].min() > 25 and summary["removed"] == 2

    def test_drop_and_rename_column(self):
        _, df = run_cleaning(F.messy_dataset(), "drop_column", {"columns": ["region"]})
        assert "region" not in df.columns
        _, df2 = run_cleaning(F.messy_dataset(), "rename_column", {"old": "score", "new": "final_score"})
        assert "final_score" in df2.columns and "score" not in df2.columns

    def test_derive_column(self):
        _, df = run_cleaning(F.messy_dataset(), "derive_column", {"new": "double_score", "left": "score", "operator": "*", "right": 2, "right_is_col": False})
        assert (df["double_score"] == df["score"] * 2).all()

    def test_summary_has_audit_fields(self):
        summary, _ = run_cleaning(F.messy_dataset(), "drop_missing", {"columns": None})
        assert {"operation", "rows_before", "rows_after", "columns"} <= set(summary)


# ── Validation ───────────────────────────────────────────────────────────────
class TestResolve:
    def _profile(self):
        return {"columns": {c: {} for c in ["price", "age", "region", "score"]}}

    def test_rejects_unknown_operation(self):
        assert resolve_operation("nuke", {}, self._profile())["ok"] is False

    def test_rejects_missing_column(self):
        assert resolve_operation("coerce_numeric", {"column": "ghost"}, self._profile())["ok"] is False

    def test_rejects_bad_strategy(self):
        assert resolve_operation("impute_missing", {"column": "age", "strategy": "wizardry"}, self._profile())["ok"] is False

    def test_accepts_valid(self):
        assert resolve_operation("coerce_numeric", {"column": "price"}, self._profile())["ok"] is True


# ── Injection safety ─────────────────────────────────────────────────────────
def test_cleaning_render_injection_safe():
    evil = "x'] = 1; import os; os.system('x'); df['y"
    code = render_operation("coerce_numeric", {"column": evil})
    assert repr(evil) in code
    assert "os.system('x')" not in code.replace(repr(evil), "")
