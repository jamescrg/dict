"""Lookup in the dictionary database built by tools/build_db.py, which
documents the tables.

A port of Dict.kt in dict-android: the two should give the same results for
the same database, so change them together.
"""

import sqlite3
import threading

from django.conf import settings

from . import text

# Matches KINDS in tools/build_db.py.
KINDS = [
    "form", "past participle", "past tense", "present tense", "plural", "comparative",
    "superlative", "subjunctive II", "subjunctive I", "imperative", "present participle",
    "zu-infinitive", "genitive", "dative", "accusative", "inflected form",
]

# Matches HEADWORD_SCORE in tools/build_db.py.
HEADWORD_SCORE = 8

# Placeholder words the index leaves out of phrases ("to go", "sich erinnern").
FILLER = {"sich", "etw", "jdn", "jdm", "jds", "jd", "jmd", "jmdn", "jmdm", "jmds", "to", "sth", "sb"}

# Sorts after every token that starts with the prefix it is appended to.
END = "￿"

_local = threading.local()


def _db():
    """One read-only connection per thread. The file is opened immutable, so
    restart the service after rebuilding it."""
    db = getattr(_local, "db", None)
    if db is None:
        db = sqlite3.connect(f"file:{settings.DICT_DB}?mode=ro&immutable=1", uri=True)
        _local.db = db
    return db


def meta(key):
    row = _db().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else ""


def line(line_id):
    """Every sub-entry of a line, as [German, English] pairs."""
    found = _load_lines([line_id]).get(line_id)
    if not found:
        return []
    de, en = found
    return [[_at(de, i), _at(en, i)] for i in range(max(len(de), len(en)))]


def search(raw):
    """{"hints": [{"lemma", "kind"}], "hits": [{"line", "sub", "de", "en"}]}.

    A hint says that lemma is the dictionary form of what was typed; kind is
    one of KINDS.
    """
    tokens = text.tokens(raw)
    if not tokens:
        return {"hints": [], "hits": []}
    found = _look_up(raw, tokens)
    if found["hits"] or found["hints"]:
        return found
    # Typed without umlauts: "ueber" for "über".
    respelled = [t.replace("ae", "a").replace("oe", "o").replace("ue", "u") for t in tokens]
    return found if respelled == tokens else _look_up(" ".join(respelled), respelled)


def _look_up(raw, tokens):
    content = [t for t in tokens if t not in FILLER] or tokens
    if len(content) == 1:
        return _word(content[0], text.low(raw.strip()) if len(tokens) == 1 else content[0])
    return _phrase(content, last_is_prefix=not raw.endswith(" "))


def _word(token, spelled):
    """spelled is the word as typed, lowercased but with its umlauts."""
    hints = _form_hints(token, spelled)
    candidates = {}  # ref -> (score, via_lemma)
    for score, ref in _postings(token, 60):
        candidates[ref] = (score, False)
    for lemma, _kind in hints:
        lemma_tokens = text.tokens(lemma)
        if not lemma_tokens:
            continue
        for score, ref in _postings(lemma_tokens[0], 25):
            candidates.setdefault(ref, (score, True))
    lines = _load_lines(ref >> 8 for ref in candidates)
    # Best first; among equals, what was typed before its lemma, and "schön"
    # before "schon" when "schön" was typed.
    ranked = []
    for ref, (score, via_lemma) in candidates.items():
        hit = _hit(ref, lines)
        if hit is None:
            continue
        exact = spelled in text.low(hit["de"]) or spelled in text.low(hit["en"])
        ranked.append(((score, via_lemma, not exact, ref), hit))
    ranked.sort(key=lambda pair: pair[0])
    hits = [hit for _key, hit in ranked]

    if len(hits) < 40 and len(token) >= 2:
        # Words that start with what was typed, in alphabetical order.
        more = list(dict.fromkeys(r for r in _completions(token, 40) if r not in candidates))
        more_lines = _load_lines(ref >> 8 for ref in more)
        hits += [h for h in (_hit(ref, more_lines) for ref in more) if h]
    return _results(hints, hits)


def _phrase(tokens, last_is_prefix):
    hints = []
    first = []
    if len(tokens) == 2:
        # A separable verb written apart: "fing an" is "anfangen".
        for lemma, kind in _form_hints(tokens[0], tokens[0]):
            joined = tokens[1] + text.fold(lemma)
            found = [ref for score, ref in _postings(joined, 25) if score < HEADWORD_SCORE]
            if not found:
                continue
            hints.append((tokens[1] + lemma, kind))
            first += found

    # Sub-entries that contain every word, ordered by their summed scores.
    totals = None
    for i, token in enumerate(tokens):
        prefix = last_is_prefix and i == len(tokens) - 1 and len(token) >= 3
        scores = _scores_by_ref(token, prefix)
        if totals is None:
            totals = scores
        else:
            totals = {ref: score + scores[ref] for ref, score in totals.items() if ref in scores}
        if not totals:
            break
    best = sorted((totals or {}).items(), key=lambda item: (item[1], item[0]))[:100]
    refs = list(dict.fromkeys(first + [ref for ref, _score in best]))
    lines = _load_lines(ref >> 8 for ref in refs)
    return _results(hints, [h for h in (_hit(ref, lines) for ref in refs) if h])


def _results(hints, hits):
    return {"hints": [{"lemma": lemma, "kind": KINDS[kind] if 0 <= kind < len(KINDS) else KINDS[0]}
                      for lemma, kind in hints],
            "hits": hits}


def _form_hints(token, spelled):
    """Up to four (lemma, kind) that token is an inflected form of."""
    rows = [(form or token, lemma, kind) for form, lemma, kind in
            _db().execute("SELECT form, lemma, kind FROM forms WHERE fold = ?", (token,))]
    # "hätte" and "hatte" fold to the same key; keep to the one typed if it is there.
    exact = [r for r in rows if r[0] == spelled]
    out, seen = [], set()
    for _spelling, lemma, kind in sorted(exact or rows, key=lambda r: r[2]):
        key = text.fold(lemma)
        if key not in seen:
            seen.add(key)
            out.append((lemma, kind))
    return out[:4]


def _postings(token, limit):
    return _db().execute(
        "SELECT score, ref FROM idx WHERE token = ? ORDER BY score, ref LIMIT ?", (token, limit)
    ).fetchall()


def _completions(prefix, limit):
    return [ref for (ref,) in _db().execute(
        "SELECT ref FROM idx WHERE token > ? AND token < ? AND score < ? "
        "ORDER BY token, score, ref LIMIT ?", (prefix, prefix + END, HEADWORD_SCORE, limit))]


def _scores_by_ref(token, prefix):
    """The best score of token (or of words starting with it) in each sub-entry."""
    if prefix:
        rows = _db().execute("SELECT ref, MIN(score) FROM idx WHERE token >= ? AND token < ? GROUP BY ref",
                             (token, token + END))
    else:
        rows = _db().execute("SELECT ref, MIN(score) FROM idx WHERE token = ? GROUP BY ref", (token,))
    return dict(rows)


def _load_lines(ids):
    """line id -> (German sub-entries, English sub-entries)."""
    ids = list(dict.fromkeys(ids))
    out = {}
    for start in range(0, len(ids), 200):
        chunk = ids[start:start + 200]
        marks = ",".join("?" * len(chunk))
        for line_id, de, en in _db().execute(f"SELECT id, de, en FROM lines WHERE id IN ({marks})", chunk):
            out[line_id] = (de.split(" | "), en.split(" | "))
    return out


def _at(parts, i):
    return parts[i] if i < len(parts) else ""


def _hit(ref, lines):
    found = lines.get(ref >> 8)
    if not found:
        return None
    de, en = found
    sub = ref & 255
    return {"line": ref >> 8, "sub": sub, "de": _at(de, sub), "en": _at(en, sub)}
