"""Generate a synthetic corpus for pipeline validation.

Not for analysis. Used to confirm the instrument runs end to end and to
see the output shape before a real corpus is available.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from . import corpus as C
from . import eras

ERA_TEMPLATES = {
    "pre_tv": [
        "We shall not fail in this. The Congress will act within the year.",
        "I ask you to remember that the work of this nation is not done.",
        "By the end of next winter we will know whether our course was right.",
        "Let us dedicate ourselves to the task before us.",
        "The months ahead will test us. They will not break us.",
    ],
    "tv_early": [
        "My friends, I want to speak with you plainly tonight.",
        "Within six months, the first of these programs will reach you.",
        "We must act, and we must act together, in the coming weeks.",
        "I have asked the Congress to move within the next ninety days.",
        "Let us begin. Let us begin now. Let us begin together.",
    ],
    "tv_color": [
        "Tonight I am asking the Congress to act within the year.",
        "In the next six months, this administration will bring forward a plan.",
        "We will not wait. We will not turn back. We will not fail.",
        "I ask your support in the weeks and months ahead.",
        "The cost of delay is greater than the cost of action.",
    ],
    "cable": [
        "I want to talk with you for a few minutes about where we are.",
        "Within a year, we will see the results of this policy.",
        "Here is what I am asking. Here is what it will cost. Here is what it will do.",
        "We have a responsibility to act before the winter.",
        "Let me be clear about what is at stake.",
    ],
    "internet": [
        "Here is what happened. Here is what we are doing about it.",
        "In the coming weeks, we will announce the next step.",
        "We act now, or we explain later why we did not.",
        "The next ninety days matter.",
        "That is the plan. That is the work. Let us begin it.",
    ],
}


def _text_for(era: str, n_sentences: int, rng: random.Random) -> str:
    pool = ERA_TEMPLATES.get(era, ERA_TEMPLATES["tv_color"])
    parts = [rng.choice(pool) for _ in range(n_sentences)]
    return " ".join(parts)


def generate(n: int = 300, seed: int = 7,
             start: date = date(1933, 3, 4),
             end: date = date(2020, 1, 20)) -> list[C.Speech]:
    """A synthetic corpus with era-appropriate framing."""
    rng = random.Random(seed)
    span = (end - start).days
    out: list[C.Speech] = []

    for i in range(n):
        d = start + timedelta(days=rng.randint(0, span))
        era = eras.classify(d)
        sentences = rng.randint(8, 30)
        text = _text_for(era, sentences, rng)
        out.append(C.Speech(
            id=f"syn-{i:04d}",
            date=d,
            text=text,
            title=f"Synthetic address {i}",
            source="synthetic",
        ))

    out.sort(key=lambda s: s.date)
    return out


def write_jsonl(speeches: list[C.Speech], path: str | Path) -> None:
    import json
    with open(path, "w", encoding="utf-8") as fh:
        for s in speeches:
            fh.write(json.dumps(s.to_dict()) + "\n")


def write_actions(speeches: list[C.Speech], path: str | Path,
                  rate: float = 0.6, lag_days: int = 120,
                  seed: int = 11) -> None:
    """Emit action dates for a subset, at the given lag."""
    import json
    rng = random.Random(seed)
    out = {}
    for s in speeches:
        if rng.random() < rate:
            out[s.id] = (s.date + timedelta(days=lag_days)).isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
