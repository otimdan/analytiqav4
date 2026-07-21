"""Pick a sensible chart type from the variables a user wants to plot.

This backs the deliberate "plot X vs Y" flow: instead of hoping the model picks a
reasonable visualization, we classify the mentioned columns and recommend a chart
form appropriate to their types (the data-viz "pick the form" step). The
recommendation is injected into the exploratory prompt as a directive.
"""
from typing import Any, NamedTuple, Optional

from app.stats_engine.variable_classifier import (
    classify_variable, classify_pair,
    NUMERIC, NUMERIC_OR_ORDINAL, CATEGORICAL, ORDINAL, DATETIME,
)

_NUMERICISH = {NUMERIC, NUMERIC_OR_ORDINAL, ORDINAL}


class ChartRecommendation(NamedTuple):
    chart_type: str          # scatter | histogram | bar | box | grouped_bar | line | heatmap
    columns: list[str]       # the variables involved, ordered (measure first where it matters)
    rationale: str           # short, human-readable — why this chart, used as the caption
    directive: str           # instruction injected into the LLM prompt


def recommend_chart(columns: list[str], profile: dict[str, Any]) -> Optional[ChartRecommendation]:
    """Return a chart recommendation for the given columns, or None if we can't
    make a confident call (0 columns, or an unsupported combination) — in which
    case the model is left to choose."""
    cols = [c for c in columns if c]
    if not cols:
        return None

    if len(cols) == 1:
        return _single(cols[0], profile)
    if len(cols) == 2:
        return _pair(cols[0], cols[1], profile)
    return _multi(cols, profile)


def _single(col: str, profile: dict[str, Any]) -> Optional[ChartRecommendation]:
    t = classify_variable(col, profile)
    if t in _NUMERICISH:
        return ChartRecommendation(
            "histogram", [col],
            f"Distribution of {col}",
            f"Plot a histogram of `{col}` to show its distribution. Label the x-axis with the variable and the y-axis 'Count'.",
        )
    if t == CATEGORICAL:
        return ChartRecommendation(
            "bar", [col],
            f"Counts by {col}",
            f"Plot a vertical bar chart of the value counts of `{col}`, sorted descending. Label the y-axis 'Count'.",
        )
    if t == DATETIME:
        return ChartRecommendation(
            "line", [col],
            f"Records over {col}",
            f"Plot a line chart of record counts over `{col}` (resample to a sensible frequency). Label the y-axis 'Count'.",
        )
    return None


def _pair(a: str, b: str, profile: dict[str, Any]) -> Optional[ChartRecommendation]:
    ta, tb = classify_variable(a, profile), classify_variable(b, profile)

    # datetime + numeric -> time series line
    if ta == DATETIME and tb in _NUMERICISH:
        return _line(a, b)
    if tb == DATETIME and ta in _NUMERICISH:
        return _line(b, a)

    # numeric x numeric -> scatter. "Y vs X" is the convention, so the
    # first-named column goes on the Y axis — matching _box ("measure by group")
    # and _line ("measure over time") below. This directive used to say "{a} vs
    # {b}" while putting `a` on the X axis, so the title and the axes contradicted
    # each other: a chart titled "exam_score vs study_hours_per_week" plotted
    # exam_score horizontally, reading as though study hours were the outcome.
    if ta in _NUMERICISH and tb in _NUMERICISH:
        return ChartRecommendation(
            "scatter", [a, b],
            f"{a} vs {b}",
            f"Plot a scatter plot with `{b}` on the x-axis and `{a}` on the y-axis. "
            f"Add a light trend line if a relationship is visible. Title it '{a} vs {b}'.",
        )

    # numeric x categorical -> box plot of the numeric grouped by the category
    if ta in _NUMERICISH and tb == CATEGORICAL:
        return _box(measure=a, group=b)
    if tb in _NUMERICISH and ta == CATEGORICAL:
        return _box(measure=b, group=a)

    # categorical x categorical -> grouped bar of counts
    if ta == CATEGORICAL and tb == CATEGORICAL:
        return ChartRecommendation(
            "grouped_bar", [a, b],
            f"{a} by {b}",
            f"Plot a grouped bar chart of counts of `{a}` split by `{b}` (use a crosstab). "
            f"Include a legend labelling the `{b}` groups.",
        )
    return None


def _multi(cols: list[str], profile: dict[str, Any]) -> Optional[ChartRecommendation]:
    types = [classify_variable(c, profile) for c in cols]
    if all(t in _NUMERICISH for t in types):
        return ChartRecommendation(
            "heatmap", cols,
            f"Correlation of {', '.join(cols)}",
            "Plot a correlation heatmap (Pearson) of these numeric columns. "
            "Annotate each cell with its correlation value and use a diverging blue-red colormap centered at 0.",
        )
    return None


def _line(time_col: str, measure: str) -> ChartRecommendation:
    return ChartRecommendation(
        "line", [time_col, measure],
        f"{measure} over {time_col}",
        f"Plot a line chart of `{measure}` over `{time_col}` (parse the dates and sort). Title it '{measure} over {time_col}'.",
    )


def _box(measure: str, group: str) -> ChartRecommendation:
    return ChartRecommendation(
        "box", [measure, group],
        f"{measure} by {group}",
        f"Plot a box plot of `{measure}` grouped by `{group}` so the distributions can be compared side by side. "
        f"Put `{group}` on the x-axis and `{measure}` on the y-axis.",
    )
