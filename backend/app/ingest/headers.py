"""Find the row that actually holds column names.

Spreadsheets exported from Excel routinely carry a merged-cell "section band"
above the real header:

    Identification,,,,,,,,,,,Population,,Demographics,,,,,Comorbidities,,...
    Study ID,First author,Year,Country,SSA subregion,Design,...

pandas takes the first row, so every real column arrives as "Unnamed: 1" …
"Unnamed: 80". A real upload did exactly this: the model burned three of its six
steps rediscovering that row 1 was the header before it could start analysing,
and the dataset profile was meaningless for the whole session.

A band row is recognisable without guessing at content: it is mostly empty,
while the row under it is mostly full.
"""

import csv
import io

# A band row is overwhelmingly empty — the label sits in the merged cell and the
# rest of the span is blank. Real headers occasionally have one or two blank
# columns, so the two thresholds are kept far apart to avoid false positives.
_BAND_MIN_EMPTY_RATIO = 0.4
_HEADER_MAX_EMPTY_RATIO = 0.15

# Only ever look at the top of the file; a band never appears deeper than this.
_MAX_SCAN_ROWS = 3


def _empty_ratio(row: list[str]) -> float:
    if not row:
        return 1.0
    return sum(1 for cell in row if not cell.strip()) / len(row)


def detect_header_row(text: str) -> int:
    """Index of the row holding the real column names. 0 when there is no band."""
    try:
        rows = list(csv.reader(io.StringIO(text)))[: _MAX_SCAN_ROWS + 1]
    except csv.Error:
        return 0

    for i in range(min(_MAX_SCAN_ROWS, len(rows) - 1)):
        this_ratio = _empty_ratio(rows[i])
        next_ratio = _empty_ratio(rows[i + 1])
        if this_ratio >= _BAND_MIN_EMPTY_RATIO and next_ratio <= _HEADER_MAX_EMPTY_RATIO:
            continue  # rows[i] is a band; keep scanning in case there are two
        return i
    return 0


def strip_header_bands(text: str) -> tuple[str, int]:
    """Drop any merged-cell band rows above the real header.

    Returns the cleaned CSV text and how many rows were removed, so the caller
    can tell the user rather than silently reshaping their file.
    """
    header_row = detect_header_row(text)
    if header_row == 0:
        return text, 0

    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows[header_row:])
    return out.getvalue(), header_row
