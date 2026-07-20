"""CSV ingestion: encoding detection and merged-cell header bands.

Both defects came from one real upload — a Mac Roman meta-analysis export whose
en dashes arrived as "Ð" and whose real column names sat under a section band,
so pandas named every column "Unnamed: N".
"""

import io

import pandas as pd
import pytest

from app.ingest.encoding import decode_csv
from app.ingest.headers import detect_header_row, strip_header_bands


# ── encoding ──────────────────────────────────────────────────────────────

def test_mac_roman_is_not_mangled_into_latin1():
    """The exact failure: latin-1 never raises, so it silently won."""
    raw = "S001,Sep 2017ÐMar 2018,LVEF ²40%; age ³65y\n".encode("latin-1")
    decoded = decode_csv(raw)
    assert decoded.encoding == "mac_roman"
    assert "Sep 2017–Mar 2018" in decoded.text
    assert "LVEF ≤40%" in decoded.text
    assert "age ≥65y" in decoded.text
    assert "Ð" not in decoded.text


def test_utf8_is_taken_without_guessing():
    decoded = decode_csv("Study,Country\nS001,Côte d'Ivoire – west\n".encode("utf-8"))
    assert decoded.encoding.startswith("utf-8")
    assert decoded.certain is True


def test_bom_is_stripped_so_the_first_column_keeps_its_name():
    decoded = decode_csv("Study ID,Country\nS001,Kenya\n".encode("utf-8-sig"))
    assert decoded.text.startswith("Study ID")


def test_windows_export_keeps_its_smart_quotes():
    decoded = decode_csv("Study,Note\nS001,“quoted” – dash; 25°C\n".encode("cp1252"))
    assert decoded.encoding == "cp1252"
    assert "“quoted” – dash; 25°C" in decoded.text


def test_accented_names_are_not_read_as_the_wrong_codepage():
    """Penalising accented letters outright broke every European name."""
    decoded = decode_csv("Author,City\nMüller,Zürich\nJosé,Bogotá\n".encode("cp1252"))
    assert "José" in decoded.text and "Bogotá" in decoded.text


def test_non_utf8_is_reported_as_uncertain():
    """Single-byte encodings are a guess; the user has to be told."""
    decoded = decode_csv("range 5–10\n".encode("mac_roman"))
    assert decoded.certain is False


# ── header bands ──────────────────────────────────────────────────────────

_BANDED = (
    "Identification,,,,,,Population,,Demographics,,\n"
    "Study ID,First author,Year,Country,Design,Setting,Analysed N,Notes,Age,Male n,Male %\n"
    "S001,Hertz,2019,Tanzania,Retro,ED,294,notes,62.4,130,44.2\n"
)


def test_merged_cell_band_is_dropped():
    cleaned, dropped = strip_header_bands(_BANDED)
    assert dropped == 1
    assert list(pd.read_csv(io.StringIO(cleaned)).columns)[:3] == ["Study ID", "First author", "Year"]


def test_without_the_fix_pandas_names_everything_unnamed():
    """Guards the premise: this is what the profiler actually saw."""
    cols = list(pd.read_csv(io.StringIO(_BANDED)).columns)
    assert cols[1].startswith("Unnamed")


@pytest.mark.parametrize(
    "csv_text",
    [
        "a,b,c\n1,2,3\n4,5,6\n",       # plain header
        "a,,c\n1,2,3\n",                # one genuinely blank column
        "value\n1\n2\n",                # single column
        "name,score\nJosé,3\n",         # nothing unusual
    ],
)
def test_normal_files_are_left_alone(csv_text):
    assert detect_header_row(csv_text) == 0
    assert strip_header_bands(csv_text)[1] == 0
