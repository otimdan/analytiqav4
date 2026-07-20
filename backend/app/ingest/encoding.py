"""Decode uploaded CSV bytes without silently corrupting them.

The previous logic was `utf-8, except UnicodeDecodeError: latin-1`. latin-1 maps
all 256 byte values, so it can never raise — which means it is not a fallback,
it is a guarantee of mojibake for any file that is not UTF-8. A real upload
(Mac Roman, exported from Excel on macOS) came through with every en dash as
"Ð", every em dash as "Ñ", "≤" as "²" and "≥" as "³". Nothing failed; the data
was just quietly wrong, and downstream grouping split "Central Africa" from
"Central Africa (Middle Africa)" into separate subgroups because of it.

Detection libraries do not solve this: charset_normalizer identifies the same
Mac Roman sample as hp_roman8, which is also wrong, just differently.

What does discriminate reliably is WHAT the high bytes become. A spreadsheet
export's high bytes are punctuation — dashes, curly quotes, ± ≤ ≥ ° µ. Decoded
with the right table they stay punctuation; decoded with the wrong one they turn
into letters ("Ð", "Å", "ý") or box-drawing ("╨", "▓"). So each candidate is
scored on what it produces rather than trusted on faith.
"""

import logging
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger("analytika")

# UTF-8 either decodes or it does not, so a success here is unambiguous and is
# taken without scoring. utf-8-sig first, to strip an Excel-written BOM that
# would otherwise become part of the first column's name.
_UNAMBIGUOUS = ("utf-8-sig", "utf-8")

# Single-byte candidates, tried only when the bytes are not valid UTF-8.
# Ordering breaks ties: Windows exports are the most common origin, and latin-1
# is last because it accepts everything and so is only ever a last resort.
_CANDIDATES = ("cp1252", "mac_roman", "latin-1")

# Typography a spreadsheet legitimately produces. Deliberately excludes
# box-drawing and block elements: cp437 turns the same bytes into "╨▓│", which
# are symbols too, and would otherwise score as well as the correct answer.
# Kept deliberately tight. Every rare character here is a false-positive risk:
# an accented byte misread by the WRONG table can land on an exotic symbol and
# collect the bonus. "·" and "‡" each did exactly that, flipping two test cases.
_TYPOGRAPHIC = set(
    "–—"        # dashes
    "‘’“”"      # curly quotes
    "±≤≥×÷≠≈"   # math
    "°µ…"       # degree, micro, ellipsis
    "€£¥"       # currency
    "™©®"
)

# Box-drawing and block elements. Real research data never contains these; a
# code-page misread (cp437/cp850) is the only way they appear.
_BOX_DRAWING_RANGES = ((0x2500, 0x257F), (0x2580, 0x259F), (0x25A0, 0x25FF))


@dataclass(frozen=True)
class DecodedCSV:
    text: str
    encoding: str
    # False when the encoding was inferred by scoring rather than proven by a
    # clean UTF-8 decode. The caller surfaces this so a researcher can eyeball
    # the text instead of trusting a guess.
    certain: bool


def _is_box_drawing(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _BOX_DRAWING_RANGES)


def _letter_in_word(text: str, i: int) -> bool:
    """True when the high letter at `i` sits inside a run of letters.

    "Müller" and "José" are real; "2017ÐMar" and a lone "Ñ" between spaces are
    punctuation that a wrong table turned into a letter. Position, not identity,
    separates them — penalising accented letters outright would misread every
    legitimately accented name.
    """
    before = text[i - 1] if i > 0 else " "
    after = text[i + 1] if i + 1 < len(text) else " "
    return before.isalpha() or after.isalpha()


def _plausibility(text: str) -> int:
    """Score a candidate decoding by what its non-ASCII characters look like."""
    score = 0
    for i, ch in enumerate(text):
        if ord(ch) < 128:
            continue
        if ch in _TYPOGRAPHIC:
            score += 2
        elif _is_box_drawing(ch):
            score -= 3
        elif unicodedata.category(ch) == "Cc":
            score -= 5
        elif unicodedata.category(ch).startswith("L"):
            if not _letter_in_word(text, i):
                score -= 3
    return score


def decode_csv(content: bytes) -> DecodedCSV:
    """Decode uploaded CSV bytes, choosing the encoding that best explains them."""
    for enc in _UNAMBIGUOUS:
        try:
            return DecodedCSV(text=content.decode(enc), encoding=enc, certain=True)
        except UnicodeDecodeError:
            continue

    scored: list[tuple[int, str, str]] = []
    for enc in _CANDIDATES:
        try:
            text = content.decode(enc)
        except UnicodeDecodeError:
            continue
        scored.append((_plausibility(text), enc, text))

    if not scored:
        raise ValueError("Could not decode the file in any supported text encoding.")

    # max() is stable, so an exact tie keeps _CANDIDATES order.
    best_score, best_enc, best_text = max(scored, key=lambda s: s[0])
    logger.warning(
        "CSV was not valid UTF-8; decoded as %s (score %d) from candidates %s",
        best_enc, best_score, {e: s for s, e, _ in scored},
    )
    return DecodedCSV(text=best_text, encoding=best_enc, certain=False)
