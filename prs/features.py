"""Rhetorical and lexical features.

Classical layer only: everything here is computable with regex and
counting, so the numbers are auditable. Metaphor-domain tagging is
deliberately NOT here — it needs a language model and belongs in a
separate assisted-annotation pass, not in the measurement path.
"""

import re
from dataclasses import dataclass

from .corpus import Speech, split_sentences

# Anaphora: a sentence opening with the same word as the previous
# sentence's opening, repeated 3+ times in a row.
OPENING = re.compile(r"^[\"']?([A-Za-z][\w'-]*)")

# Tricolon: three parallel items joined by commas with a final "and"/"or".
TRICOLON = re.compile(
    r"\b\w+(?:\s+\w+){0,3},\s+\w+(?:\s+\w+){0,3},\s+(?:and|or)\s+\w+",
    re.I,
)

# First-person plural vs singular vs second person.
PRONOUNS = {
    "we": re.compile(r"\b(we|us|our|ours|ourselves)\b", re.I),
    "i": re.compile(r"\b(i|me|my|mine|myself)\b", re.I),
    "you": re.compile(r"\b(you|your|yours|yourself)\b", re.I),
}

# Direct address to the audience — the fireside register.
ADDRESS = re.compile(
    r"\b(my friends|my fellow|fellow Americans|my countrymen|"
    r"you and i|let us|let's)\b",
    re.I,
)

WORD = re.compile(r"[A-Za-z][\w'-]*")


@dataclass(frozen=True)
class FeatureSet:
    sentences: int
    words: int
    mean_sentence_len: float
    sentence_len_stdev: float
    anaphora_runs: int
    tricolon_count: int
    pronoun_share: dict
    address_count: int
    type_token_ratio: float


def _anaphora_runs(sentences: list[str]) -> int:
    """Count runs of 3+ consecutive sentences sharing an opening word."""
    runs = 0
    streak = 1
    prev = None
    for s in sentences:
        m = OPENING.match(s.strip())
        head = m.group(1).lower() if m else None
        if head and head == prev:
            streak += 1
        else:
            if streak >= 3:
                runs += 1
            streak = 1
            prev = head
    if streak >= 3:
        runs += 1
    return runs


def extract(speech: Speech) -> FeatureSet:
    text = speech.text
    sentences = split_sentences(text)
    words = WORD.findall(text)
    n_words = len(words) or 1

    lengths = [len(WORD.findall(s)) for s in sentences] or [0]
    mean_len = sum(lengths) / len(lengths)
    var = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)

    share = {k: round(len(rx.findall(text)) / n_words, 4)
             for k, rx in PRONOUNS.items()}

    return FeatureSet(
        sentences=len(sentences),
        words=len(words),
        mean_sentence_len=round(mean_len, 2),
        sentence_len_stdev=round(var ** 0.5, 2),
        anaphora_runs=_anaphora_runs(sentences),
        tricolon_count=len(TRICOLON.findall(text)),
        pronoun_share=share,
        address_count=len(ADDRESS.findall(text)),
        type_token_ratio=round(len({w.lower() for w in words}) / n_words, 4),
    )
