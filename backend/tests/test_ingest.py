"""CSV ingestion: encoding detection and merged-cell header bands.

Both defects came from one real upload — a Mac Roman meta-analysis export whose
en dashes arrived as "Ð" and whose real column names sat under a section band,
so pandas named every column "Unnamed: N".
"""

import asyncio
import csv
import io
import tracemalloc

import pandas as pd
import pytest
from fastapi import HTTPException

from app.auth import AuthUser
from app.config import MAX_UPLOAD_BYTES
from app.ingest.encoding import decode_csv
from app.ingest.headers import detect_header_row, strip_header_bands
from app.routers.session import upload_dataset


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


# ── upload size guard ─────────────────────────────────────────────────────


class _StubUpload:
    """Enough of Starlette's UploadFile for the size guard, which runs before
    the handler touches the DB or a sandbox."""

    def __init__(self, size: int | None, content: bytes = b""):
        self.filename = "big.csv"
        self.size = size
        self._content = content

    async def read(self) -> bytes:
        return self._content


def _upload(stub: _StubUpload) -> None:
    asyncio.run(upload_dataset(file=stub, mode="explore", user=AuthUser(id="size-guard")))


def test_oversized_upload_is_rejected_before_it_is_read():
    stub = _StubUpload(size=MAX_UPLOAD_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        _upload(stub)
    assert exc.value.status_code == 413


def test_header_scan_does_not_read_the_whole_file():
    """detect_header_row scans the top only. It used to materialise every row and
    then slice, which was ~13x the file size in short-lived str objects."""
    rows = 200_000
    text = "a,b,c\n" + "".join(f"{i},{i},{i}\n" for i in range(rows))

    tracemalloc.start()
    detect_header_row(text)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Scanning 4 rows should cost kilobytes, not a multiple of the input.
    assert peak < len(text) / 10, f"scan allocated {peak:,} bytes for a {len(text):,} byte file"


def test_a_malformed_row_below_the_scan_window_does_not_500():
    """detect_header_row no longer sees deep rows, so strip_header_bands is where
    a late csv.Error surfaces — it must fall back, not raise."""
    banded = "Section,,,\nid,name,score,note\n"
    huge_field = "x" * (csv.field_size_limit() + 1)
    text = banded + f'1,ok,5,"{huge_field}\n'  # unterminated quote -> csv.Error

    result, dropped = strip_header_bands(text)
    assert (result, dropped) == (text, 0)


def test_size_is_rechecked_against_the_bytes_read():
    """Starlette leaves .size unset for some clients — the read must still be bounded."""
    stub = _StubUpload(size=None, content=b"x" * (MAX_UPLOAD_BYTES + 1))
    with pytest.raises(HTTPException) as exc:
        _upload(stub)
    assert exc.value.status_code == 413
