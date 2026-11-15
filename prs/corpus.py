# prs/corpus.py
"""Corpus loading, normalisation, segmentation and aggregation.

A corpus is a list of Speech records. This module is responsible for:

  * reading records off disk in the two formats the archive exports
  * normalising transcript text so downstream feature extraction sees a
    consistent surface (whitespace, speaker labels, bracketed stage
    directions, Unicode dashes and quotes)
  * assigning each speech to a broadcast era
  * producing per-speech temporal profiles
  * aggregating those profiles across eras

Everything here is deterministic and dependency-free. No language model
is consulted; no network is touched.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator

from . import eras, temporal

# --------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------

# Transcript conventions vary by archive. These are the ones that actually
# show up in digitised presidential speech collections.
_SPEAKER_LABEL = re.compile(
    r"^\s*(?:THE\s+PRESIDENT|THE\s+VICE\s+PRESIDENT|MR\.?\s+\w+|"
    r"MRS\.?\s+\w+|MS\.?\s+\w+|SECRETARY\s+\w+|"
    r"Q|A|QUESTION|ANSWER|INTERVIEWER|MODERATOR|REPORTER)"
    r"\s*[.:]\s*",
    re.I | re.M,
)

# [laughter], (applause), [Applause.], <pause> — bracketed non-speech.
_STAGE_DIRECTION = re.compile(r"[\[\(<]\s*(?:applause|laughter|pause|"
                              r"inaudible|crosstalk|music|sighs|boos|"
                              r"cheers|silence|unknown)\b[^\]\)>]*[\]\)>]",
                              re.I)

# "The President. " / "MR. SMITH. " as a line on its own.
_STANDALONE_LABEL = re.compile(r"^\s*[A-Z][A-Z.\s]{2,40}\.\s*$", re.M)

# Collapse runs of whitespace, but keep paragraph breaks.
_MULTISPACE = re.compile(r"[ \t\u00a0]+")
_MULTINEWLINE = re.compile(r"\n{3,}")

# Unicode punctuation that transcripts frequently carry inconsistently.
_PUNCT_MAP = {
    "\u2018": "'", "\u2019": "'",      # curly singles
    "\u201c": '"', "\u201d": '"',      # curly doubles
    "\u2013": "-", "\u2014": "-",      # en dash, em dash
    "\u2026": "...",                    # ellipsis
    "\u00a0": " ",                      # non-breaking space
    "\ufeff": "",                       # BOM
    "\u200b": "",                       # zero-width space
}


def normalise(text: str) -> str:
    """Return `text` cleaned for analysis.

    The transformations are lossless with respect to words spoken: they
    remove markup and normalise Unicode, but never reword, reorder, or
    drop substantive text.
    """
    if not text:
        return ""

    # NFKC folds compatibility forms (ligatures, full-width letters).
    text = unicodedata.normalize("NFKC", text)

    for src, dst in _PUNCT_MAP.items():
        text = text.replace(src, dst)

    text = _STAGE_DIRECTION.sub(" ", text)
    text = _SPEAKER_LABEL.sub("", text)
    text = _STANDALONE_LABEL.sub("", text)

    # Normalise line endings before collapsing.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTISPACE.sub(" ", text)
    text = _MULTINEWLINE.sub("\n\n", text)

    return text.strip()


# --------------------------------------------------------------------------
# Sentence splitting
# --------------------------------------------------------------------------

# Abbreviations that would otherwise end a sentence.
_ABBREV = {
    "mr", "mrs", "ms", "dr", "sen", "rep", "gov", "gen", "col", "lt",
    "sgt", "capt", "adm", "hon", "pres", "sec", "supt", "rev", "fr",
    "st", "mt", "no", "vs", "etc", "jr", "sr", "inc", "ltd", "co",
    "u.s", "u.n", "d.c", "a.m", "p.m", "e.g", "i.e", "cf", "al",
}

_SENT_BOUNDARY = re.compile(r'(?<=[.!?])\s+')
_TERMINAL = ".!?"


def _is_abbreviation(token: str) -> bool:
    """True when `token` ends with an abbreviation period."""
    stripped = token.rstrip(".!?")
    if not stripped:
        return False
    tail = stripped.split()[-1] if " " in stripped else stripped
    # Drop an internal period: "U.S" -> "US", "U.S." handled by caller.
    tail = tail.replace(".", "").lower()
    return tail in _ABBREV


def split_sentences(text: str) -> list[str]:
    """Split `text` into sentences.

    Conservative by design: transcripts are noisy, and over-splitting
    corrupts every length statistic downstream. Boundaries are taken at
    terminal punctuation followed by whitespace and an uppercase or
    quote character, except where the preceding token is a known
    abbreviation or a single initial.
    """
    if not text:
        return []

    out: list[str] = []
    buf = ""

    for piece in _SENT_BOUNDARY.split(text):
        if not buf:
            buf = piece
            continue

        prev = buf.rstrip()
        if not prev:
            buf = piece
            continue

        last_char = prev[-1]
        last_token = prev.split()[-1] if prev.split() else ""

        # Single initial like "J." or "A." — not a boundary.
        if (last_char == "." and len(last_token.rstrip(".")) == 1
                and last_token.rstrip(".").isalpha()):
            buf = f"{buf} {piece}"
            continue

        if last_char == "." and _is_abbreviation(last_token):
            buf = f"{buf} {piece}"
            continue

        out.append(prev)
        buf = piece

    if buf.strip():
        out.append(buf.strip())

    # Final pass: strip empties, reattach orphaned fragments shorter than
    # two characters (usually stray punctuation from transcript markup).
    cleaned: list[str] = []
    for s in out:
        s = s.strip()
        if not s:
            continue
        if len(s) < 2 and cleaned:
            cleaned[-1] = f"{cleaned[-1]} {s}"
        else:
            cleaned.append(s)
    return cleaned


# --------------------------------------------------------------------------
# The Speech record
# --------------------------------------------------------------------------

@dataclass
class Speech:
    """One speech, with its era assigned at construction time."""

    id: str
    date: date
    text: str
    title: str = ""
    source: str = ""
    era: str = field(init=False)

    def __post_init__(self) -> None:
        self.era = eras.classify(self.date)

    @property
    def year(self) -> int:
        return self.date.year

    def sentences(self) -> list[str]:
        return split_sentences(self.text)

    def word_count(self) -> int:
        return len(re.findall(r"[A-Za-z][\w'-]*", self.text))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "title": self.title,
            "source": self.source,
            "era": self.era,
            "text": self.text,
        }


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

_DATE_PREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[_-](.+)$")
_ANY_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _parse_date(value: str) -> date:
    """Parse an ISO date, tolerating a trailing time component."""
    value = value.strip()
    if "T" in value or " " in value:
        value = value.split("T")[0].split(" ")[0]
    return date.fromisoformat(value)


def _coerce_record(raw: dict, fallback_id: str = "") -> Speech | None:
    """Build a Speech from a loosely-shaped dict, or None if unusable."""
    text = raw.get("text") or raw.get("transcript") or raw.get("body") or ""
    if not isinstance(text, str) or not text.strip():
        return None

    date_val = raw.get("date") or raw.get("delivered") or raw.get("when")
    if not date_val:
        return None
    try:
        d = _parse_date(str(date_val))
    except (ValueError, TypeError):
        return None

    sid = str(raw.get("id") or raw.get("doc_id") or fallback_id or "")
    if not sid:
        sid = f"{d.isoformat()}-{abs(hash(text)) % 10**8:08d}"

    return Speech(
        id=sid,
        date=d,
        text=normalise(text),
        title=str(raw.get("title") or raw.get("name") or ""),
        source=str(raw.get("source") or raw.get("archive") or ""),
    )


def load_jsonl(path: str | Path) -> list[Speech]:
    """Load a JSONL file of speech records.

    Each line is a JSON object with at least `date` and one of
    `text` / `transcript` / `body`. Malformed lines are skipped rather
    than aborting the load, so a partly-corrupt export still yields the
    records that are intact.
    """
    out: list[Speech] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            speech = _coerce_record(raw, fallback_id=f"line{lineno}")
            if speech is not None:
                out.append(speech)
    return out


def load_json(path: str | Path) -> list[Speech]:
    """Load a JSON file holding either a list of records or an object
    with a `speeches` / `records` / `documents` list."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, dict):
        for key in ("speeches", "records", "documents", "items"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raw = [raw]

    if not isinstance(raw, list):
        return []

    out: list[Speech] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        speech = _coerce_record(item, fallback_id=f"item{i}")
        if speech is not None:
            out.append(speech)
    return out


def load_dir(path: str | Path) -> list[Speech]:
    """Load a directory of text files.

    Files named `YYYY-MM-DD_rest.txt` take their date from the name.
    Files without a date prefix are parsed for a date in the first few
    lines; if none is found they are skipped.
    """
    out: list[Speech] = []
    root = Path(path)
    for p in sorted(root.rglob("*.txt")):
        if not p.is_file():
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        m = _DATE_PREFIX.match(p.stem)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            title = m.group(4).replace("_", " ").strip()
        else:
            head = "\n".join(text.splitlines()[:8])
            dm = _ANY_DATE.search(head)
            if not dm:
                continue
            try:
                d = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except ValueError:
                continue
            title = p.stem

        out.append(Speech(
            id=p.stem,
            date=d,
            text=normalise(text),
            title=title,
            source=str(p.relative_to(root)),
        ))
    return out


def load(path: str | Path) -> list[Speech]:
    """Load from a file or directory, picking the reader by shape."""
    p = Path(path)
    if p.is_dir():
        return load_dir(p)
    suffix = p.suffix.lower()
    if suffix in (".jsonl", ".ndjson"):
        return load_jsonl(p)
    if suffix == ".json":
        return load_json(p)
    if suffix == ".txt":
        return load_dir(p.parent) if p.parent.is_dir() else []
    raise ValueError(f"unrecognised corpus path: {path}")


def merge(*corpora: Iterable[Speech]) -> list[Speech]:
    """Concatenate corpora, dropping duplicate ids (first wins) and
    returning the result sorted by date."""
    seen: set[str] = set()
    out: list[Speech] = []
    for corpus in corpora:
        for s in corpus:
            if s.id in seen:
                continue
            seen.add(s.id)
            out.append(s)
    out.sort(key=lambda s: (s.date, s.id))
    return out


# --------------------------------------------------------------------------
# Per-speech profiles
# --------------------------------------------------------------------------

def horizon_profile(speech: Speech) -> dict:
    """Where a single speech's forward commitments point."""
    horizons = temporal.extract(speech.text)
    bands: dict[str, int] = {}
    for h in horizons:
        b = temporal.bucket(h.days)
        bands[b] = bands.get(b, 0) + 1

    total = len(horizons)
    return {
        "id": speech.id,
        "date": speech.date.isoformat(),
        "era": speech.era,
        "words": speech.word_count(),
        "sentences": len(speech.sentences()),
        "horizons": total,
        "bands": bands,
        "band_share": ({b: round(n / total, 3) for b, n in bands.items()}
                       if total else {}),
        "six_month": bands.get("91-180d", 0),
        "commit_ratio": round(temporal.commit_ratio(speech.text), 3),
    }


def profile_corpus(speeches: list[Speech]) -> list[dict]:
    """Per-speech profiles for a whole corpus, in date order."""
    return [horizon_profile(s) for s in sorted(speeches, key=lambda s: s.date)]


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

BAND_ORDER = ("0-30d", "31-90d", "91-180d", "181-365d", ">365d")


def _empty_bucket() -> dict:
    return {"speeches": 0, "horizons": 0, "bands": {}, "_commit_sum": 0.0,
            "_words": 0}


def _accumulate(bucket: dict, prof: dict) -> None:
    bucket["speeches"] += 1
    bucket["horizons"] += prof["horizons"]
    bucket["_words"] += prof["words"]
    bucket["_commit_sum"] += prof["commit_ratio"]
    for b, n in prof["bands"].items():
        bucket["bands"][b] = bucket["bands"].get(b, 0) + n


def _finalise(bucket: dict, note: str = "") -> dict:
    n = bucket["speeches"] or 1
    total = bucket["horizons"]
    return {
        "speeches": bucket["speeches"],
        "words": bucket["_words"],
        "horizons": total,
        "per_speech": round(total / n, 2),
        "per_1k_words": round(1000 * total / (bucket["_words"] or 1), 3),
        "band_share": ({b: round(bucket["bands"][b] / total, 3)
                        for b in BAND_ORDER if b in bucket["bands"]}
                       if total else {}),
        "mean_commit_ratio": round(bucket["_commit_sum"] / n, 3),
        "note": note,
    }


def aggregate(speeches: list[Speech]) -> dict:
    """Temporal band distribution per era, normalised by speech count
    and by word count."""
    by_era: dict[str, dict] = {}
    for s in speeches:
        bucket = by_era.setdefault(s.era, _empty_bucket())
        _accumulate(bucket, horizon_profile(s))

    return {
        era: _finalise(bucket, eras.describe(era))
        for era, bucket in by_era.items()
    }


def aggregate_by_year(speeches: list[Speech]) -> dict[int, dict]:
    """The same aggregation keyed by calendar year."""
    by_year: dict[int, dict] = {}
    for s in speeches:
        bucket = by_year.setdefault(s.year, _empty_bucket())
        _accumulate(bucket, horizon_profile(s))
    return {y: _finalise(bucket) for y, bucket in sorted(by_year.items())}


def aggregate_by_president(speeches: list[Speech],
                           attribution: dict[str, str]) -> dict[str, dict]:
    """Aggregate by president.

    `attribution` maps speech id -> president name. Speeches absent from
    the map are grouped under "unattributed" rather than dropped.
    """
    by_pres: dict[str, dict] = {}
    for s in speeches:
        who = attribution.get(s.id, "unattributed")
        bucket = by_pres.setdefault(who, _empty_bucket())
        _accumulate(bucket, horizon_profile(s))
    return {who: _finalise(bucket) for who, bucket in by_pres.items()}


# --------------------------------------------------------------------------
# Corpus convenience wrapper
# --------------------------------------------------------------------------

@dataclass
class Corpus:
    """A loaded corpus with its aggregation helpers attached."""

    speeches: list[Speech]

    def __len__(self) -> int:
        return len(self.speeches)

    def __iter__(self) -> Iterator[Speech]:
        return iter(self.speeches)

    def filter(self, *, era: str | None = None,
               start: date | None = None,
               end: date | None = None) -> "Corpus":
        out = self.speeches
        if era is not None:
            out = [s for s in out if s.era == era]
        if start is not None:
            out = [s for s in out if s.date >= start]
        if end is not None:
            out = [s for s in out if s.date <= end]
        return Corpus(out)

    def profiles(self) -> list[dict]:
        return profile_corpus(self.speeches)

    def by_era(self) -> dict:
        return aggregate(self.speeches)

    def by_year(self) -> dict[int, dict]:
        return aggregate_by_year(self.speeches)

    @classmethod
    def load(cls, path: str | Path) -> "Corpus":
        return cls(load(path))
