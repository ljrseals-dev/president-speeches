"""Passage-level segmentation.

Splits a speech into runs by horizon band, so you can see the shape of a
speech over time rather than only its totals.
"""

from dataclasses import dataclass

from . import temporal
from .corpus import Speech, split_sentences


@dataclass(frozen=True)
class Segment:
    index: int
    text: str
    horizons: int
    bands: dict
    commit_ratio: float


def split(speech: Speech, window: int = 5) -> list[Segment]:
    """Slide a window of `window` sentences across the speech.

    Overlapping windows; each segment carries the temporal profile of
    the sentences it covers.
    """
    sents = split_sentences(speech.text)
    out: list[Segment] = []
    if not sents:
        return out
    step = max(1, window // 2)
    for i in range(0, len(sents), step):
        chunk = " ".join(sents[i:i + window])
        if not chunk:
            continue
        hs = temporal.extract(chunk)
        bands: dict[str, int] = {}
        for h in hs:
            b = temporal.bucket(h.days)
            bands[b] = bands.get(b, 0) + 1
        out.append(Segment(
            index=i,
            text=chunk,
            horizons=len(hs),
            bands=bands,
            commit_ratio=round(temporal.commit_ratio(chunk), 3),
        ))
    return out


def curve(speech: Speech, window: int = 5) -> list[dict]:
    """Just the numeric shape: position -> six-month horizon count."""
    return [{"index": s.index, "six_month": s.bands.get("91-180d", 0),
             "horizons": s.horizons, "commit_ratio": s.commit_ratio}
            for s in split(speech, window)]
