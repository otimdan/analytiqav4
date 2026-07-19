"""Unit tests for confirmatory variable resolution (F1 trust fix).

A mistyped / nonexistent column must NOT be silently replaced with a context
variable — that answered the wrong question with a confident, verified-looking
result (e.g. "test foobar and bp" ran age-vs-bp). Context variables may only fill
in for a genuine follow-up that names NO column.
"""
from app.regimes.confirmatory import resolve_pair_variables, _format_group_descriptives

PROFILE = {"columns": {"bp": {}, "age": {}, "region": {}, "treatment": {}}}


def test_two_named_columns_resolve():
    vars_, clar = resolve_pair_variables("compare bp across region", PROFILE, None)
    assert clar is None
    assert set(vars_) == {"bp", "region"}


def test_no_columns_named_uses_focus():
    # A genuine follow-up ("is that significant?") reuses the last-worked-on pair.
    vars_, clar = resolve_pair_variables("is that significant?", PROFILE, ["bp", "age"])
    assert clar is None
    assert vars_ == ["bp", "age"]


def test_mistyped_column_not_substituted_even_with_focus():
    # THE FIX: named a real column (bp) + a bogus one (foobar) → ask, never
    # silently borrow 'age' from focus and answer a different question.
    vars_, clar = resolve_pair_variables("run a test on foobar and bp", PROFILE, ["age", "bp"])
    assert vars_ is None
    assert clar and "bp" in clar and "mistype" in clar.lower()


def test_single_named_column_asks_for_second():
    vars_, clar = resolve_pair_variables("test bp", PROFILE, None)
    assert vars_ is None
    assert "second column" in clar.lower()


def test_no_columns_no_focus_asks_for_two():
    vars_, clar = resolve_pair_variables("run a test", PROFILE, None)
    assert vars_ is None
    assert "two columns" in clar.lower()


# ── F2 fix: group means/medians labelled deterministically (not by the LLM) ──

def test_group_descriptives_pin_labels_to_correct_values():
    groups = [
        {"label": "east", "center_type": "mean", "center": 134.50, "n": 65},
        {"label": "north", "center_type": "mean", "center": 122.87, "n": 52},
        {"label": "south", "center_type": "mean", "center": 128.83, "n": 63},
    ]
    s = _format_group_descriptives(groups)
    assert s.startswith("**Group means:**")
    assert "east: mean = 134.50, n = 65" in s
    assert "north: mean = 122.87, n = 52" in s  # the value the LLM kept mislabeling


def test_group_descriptives_medians_and_empty():
    med = _format_group_descriptives([
        {"label": "A", "center_type": "median", "center": 17321.0, "n": 90},
        {"label": "B", "center_type": "median", "center": 22159.0, "n": 90},
    ])
    assert "**Group medians:**" in med and "B: median = 22159.00, n = 90" in med
    assert _format_group_descriptives(None) == ""
    assert _format_group_descriptives([]) == ""
