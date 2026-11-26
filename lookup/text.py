"""Text normalisation. Must stay in step with low(), fold() and tokens() in
tools/build_db.py (and with Text.kt in dict-android)."""

import re
import unicodedata

_WORD = re.compile(r"[^\W_]+")


def low(s):
    """Lowercase, with ß written as ss."""
    return s.lower().replace("ß", "ss")


def fold(s):
    """low(), with accents and umlauts removed: "Häuser" becomes "hauser"."""
    s = unicodedata.normalize("NFD", low(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tokens(s):
    return _WORD.findall(fold(s))
