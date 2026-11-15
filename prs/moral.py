"""
Moral-language analyzer.

Measures the distribution of moral-foundations vocabulary in text.
Outputs descriptive counts and proportions. Does not score texts
as good/bad, does not rank authors, does not output a verdict.

Changes in this version:
  - Negation detection with a clause-bounded two-token window.
  - Negated hits are excluded from foundation totals and reported
    separately, so dropped mass is visible.
  - Pluggable lexicon: seed dict (default) or MFD 2.0 from a local file.

Still descriptive. No verdict, no ranking, no moral score.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# --- Lexicon ----------------------------------------------------------------
# Seed terms. Over-fires; replace with MFD 2.0 for corpus work.

SEED_LEXICON: dict[str, dict[str, list[str]]] = {
    "care": {
        "virtue": ["care", "caring", "protect", "protecting", "compassion",
                   "kind", "kindness", "nurture", "nurturing", "safe",
                   "safety", "shelter", "empathy", "empathetic"],
        "vice":   ["harm", "harming", "hurt", "hurting", "cruel", "cruelty",
                   "abuse", "abusing", "neglect", "neglecting", "suffer",
                   "suffering", "endanger", "endangering"],
    },
    "fairness": {
        "virtue": ["fair", "fairness", "equal", "equality", "justice", "just",
                   "rights", "reciprocity", "impartial", "balanced",
                   "proportional"],
        "vice":   ["unfair", "unfairness", "unequal", "inequality", "injustice",
                   "unjust", "cheat", "cheating", "cheater", "bias", "biased",
                   "discriminate", "discrimination", "exploit", "exploiting"],
    },
    "loyalty": {
        "virtue": ["loyal", "loyalty", "allegiance", "patriot", "patriotism",
                   "solidarity", "comrade", "comrades", "unity", "united",
                   "faithful", "devotion", "devoted"],
        "vice":   ["betray", "betrayal", "betraying", "traitor", "treason",
                   "treasonous", "disloyal", "disloyalty", "treachery",
                   "treacherous", "defect", "defector", "subvert",
                   "subversion"],
    },
    "authority": {
        "virtue": ["authority", "obey", "obedience", "respect", "respectful",
                   "duty", "dutiful", "lawful", "law", "order", "ordered",
                   "tradition", "traditional", "hierarchy", "legitimate"],
        "vice":   ["disobey", "disobedience", "disobedient", "rebel",
                   "rebellion", "rebellious", "chaos", "chaotic", "anarchy",
                   "unlawful", "subversive", "insubordinate"],
    },
    "sanctity": {
        "virtue": ["sacred", "holy", "pure", "purity", "chaste", "chastity",
                   "clean", "cleanliness", "wholesome", "decency", "decent",
                   "elevated", "divine", "blessed"],
        "vice":   ["profane", "profanity", "impure", "impurity", "unchaste",
                   "dirty", "filth", "filthy", "disgust", "disgusting",
                   "degraded", "degradation", "corrupt", "corruption",
                   "sinful", "sin"],
    },
}


def load_mfd(path: str | Path) -> dict[str, dict[str, list[str]]]:
    """Load MFD 2.0-shaped JSON: {foundation: {virtue: [...], vice: [...]}}."""
    data = json.loads(Path(path).read_text())
    out: dict[str, dict[str, list[str]]] = {}
    for foundation, poles in data.items():
        out[foundation] = {
            "virtue": [t.lower() for t in poles.get("virtue", [])],
            "vice":   [t.lower() for t in poles.get("vice", [])],
        }
    return out


# --- Negation cues ----------------------------------------------------------

NEGATION_CUES: frozenset[str] = frozenset({
    "not", "no", "never", "none", "nothing", "neither", "nor", "without",
    "cannot", "can't", "don't", "doesn't", "didn't", "won't", "wouldn't",
    "shouldn't", "isn't", "aren't", "wasn't", "weren't", "ain't", "n't",
    "hardly", "scarcely", "barely", "rarely", "seldom",
})

CLAUSE_BOUNDARY: frozenset[str] = frozenset({
    ",", ";", ":", "—", "–", "-", "and", "or", "but", "yet", "so",
    "because", "although", "though", "while", "whereas", "if", "unless",
    "that", "which", "who", "whom", "whose",
})

NEGATION_WINDOW = 2


# --- Data structures --------------------------------------------------------

@dataclass
class FoundationHit:
    foundation: str
    polarity: str            # "virtue" | "vice"
    term: str
    count: int
    positions: list[int] = field(default_factory=list)
    negated: bool = False
    negation_cue: str | None = None


@dataclass
class AnalysisResult:
    total_tokens: int
    total_moral_tokens: int
    hits: list[FoundationHit]
    negated_hits: list[FoundationHit]
    foundation_totals: dict[str, int]
    foundation_shares: dict[str, float]
    virtue_vice_ratio: dict[str, float]
    moral_density: float
    negated_token_count: int
    negated_share: float

    def summary(self) -> str:
        lines = [
            f"tokens: {self.total_tokens}",
            f"moral tokens (scored): {self.total_moral_tokens} "
            f"({self.moral_density:.3%} density)",
            f"negated hits excluded: {self.negated_token_count} "
            f"({self.negated_share:.2%} of moral hits)",
            "",
            "foundation shares (of scored moral tokens):",
        ]
        for f, share in sorted(self.foundation_shares.items(),
                               key=lambda x: -x[1]):
            vv = self.virtue_vice_ratio.get(f, float("nan"))
            lines.append(f"  {f:<10} {share:6.2%}   virtue/vice ratio: {vv:.2f}")
        if self.negated_share > 0.10:
            lines.append("")
            lines.append("  NOTE: negated share above 10% — read raw shares "
                         "with the negation report in mind.")
        return "\n".join(lines)


# --- Matcher compilation ----------------------------------------------------

def _compile_index(
    lexicon: dict[str, dict[str, list[str]]]
) -> dict[str, list[tuple[str, str, re.Pattern]]]:
    idx: dict[str, list[tuple[str, str, re.Pattern]]] = {}
    for foundation, poles in lexicon.items():
        for polarity, terms in poles.items():
            for t in terms:
                idx.setdefault(t, []).append(
                    (foundation, polarity,
                     re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE))
                )
    return idx


_TOKEN_RE = re.compile(r"\b[\w']+\b|[,;:—–-]")


def _negation_in_window(tokens: list[str], hit_pos: int) -> str | None:
    """Return the negation cue scoping over tokens[hit_pos], or None."""
    cues: list[str] = []
    for offset in range(1, NEGATION_WINDOW + 1):
        j = hit_pos - offset
        if j < 0:
            break
        tok = tokens[j].lower()
        if tok in CLAUSE_BOUNDARY:
            break
        if tok in NEGATION_CUES:
            cues.append(tok)
    if not cues:
        return None
    if len(cues) > 1:
        return "__ambiguous__"
    return cues[0]


def analyze(
    text: str,
    lexicon: dict[str, dict[str, list[str]]] | None = None,
) -> AnalysisResult:
    """
    Measure moral-foundations vocabulary in `text`.

    Negated hits are excluded from foundation totals and virtue/vice
    ratios, and reported separately. They are NOT flipped: rhetorical
    negation in political speech ("we will not tolerate X") does not
    reliably invert valence, so flipping would overstate the virtue
    pole. Exclusion is the honest default.

    Ceiling on the method: bag-of-terms cannot recover whether "we
    will not X" asserts X's importance or X's absence. Treat output
    as a distribution over moral vocabulary, not a moral reading.
    """
    lex = lexicon if lexicon is not None else SEED_LEXICON
    index = _compile_index(lex)

    tokens = _TOKEN_RE.findall(text)
    total_tokens = sum(1 for t in tokens if t not in CLAUSE_BOUNDARY
                       and not t.isspace())

    scored: dict[tuple[str, str, str], list[int]] = {}
    negated: dict[tuple[str, str, str, str], list[int]] = {}

    for pos, tok in enumerate(tokens):
        lower = tok.lower()
        for foundation, polarity, pattern in index.get(lower, []):
            if not pattern.fullmatch(tok):
                continue
            cue = _negation_in_window(tokens, pos)
            if cue is None:
                scored.setdefault((foundation, polarity, lower), []).append(pos)
            else:
                negated.setdefault((foundation, polarity, lower, cue),
                                   []).append(pos)

    hits: list[FoundationHit] = []
    foundation_totals: Counter[str] = Counter()
    pole_totals: dict[str, Counter[str]] = {}

    for (foundation, polarity, term), positions in scored.items():
        hits.append(FoundationHit(
            foundation=foundation, polarity=polarity, term=term,
            count=len(positions), positions=positions,
        ))
        foundation_totals[foundation] += len(positions)
        pole_totals.setdefault(foundation, Counter())[polarity] += len(positions)

    negated_hits: list[FoundationHit] = []
    for (foundation, polarity, term, cue), positions in negated.items():
        negated_hits.append(FoundationHit(
            foundation=foundation, polarity=polarity, term=term,
            count=len(positions), positions=positions,
            negated=True,
            negation_cue=None if cue == "__ambiguous__" else cue,
        ))

    total_moral = sum(foundation_totals.values())
    total_moral_incl_neg = total_moral + sum(h.count for h in negated_hits)

    foundation_shares = {
        f: (c / total_moral if total_moral else 0.0)
        for f, c in foundation_totals.items()
    }

    virtue_vice_ratio: dict[str, float] = {}
    for f, poles in pole_totals.items():
        v = poles.get("virtue", 0)
        vic = poles.get("vice", 0)
        virtue_vice_ratio[f] = (
            float("inf") if vic == 0 and v > 0
            else 0.0 if v == 0 and vic == 0
            else v / vic
        )

    return AnalysisResult(
        total_tokens=total_tokens,
        total_moral_tokens=total_moral,
        hits=sorted(hits, key=lambda h: (-h.count, h.foundation, h.term)),
        negated_hits=sorted(negated_hits,
                            key=lambda h: (-h.count, h.foundation, h.term)),
        foundation_totals=dict(foundation_totals),
        foundation_shares=foundation_shares,
        virtue_vice_ratio=virtue_vice_ratio,
        moral_density=(total_moral / total_tokens if total_tokens else 0.0),
        negated_token_count=sum(h.count for h in negated_hits),
        negated_share=(sum(h.count for h in negated_hits) / total_moral_incl_neg
                       if total_moral_incl_neg else 0.0),
    )


def analyze_corpus(
    texts: Iterable[str],
    lexicon: dict[str, dict[str, list[str]]] | None = None,
) -> AnalysisResult:
    return analyze("\n".join(texts), lexicon=lexicon)
