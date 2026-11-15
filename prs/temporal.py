"""Forward-looking horizon extraction.

Finds expressions that point at a future action and converts them to a
day-count, so a passage can be bucketed by how far ahead it commits.
"""

import re
from dataclasses import dataclass

# Spellings that appear in speech transcripts.
NUMWORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "eighteen": 18, "twenty-four": 24,
}

UNIT_DAYS = {
    "day": 1, "week": 7, "fortnight": 14, "month": 30,
    "quarter": 91, "year": 365,
}

# "within six months", "in the next 90 days", "over the coming weeks"
DURATION = re.compile(
    r"\b(?:within|in|after|over|inside)\s+"
    r"(?:the\s+)?(?:next\s+|coming\s+|following\s+)?"
    r"(\d{1,3}|" + "|".join(NUMWORDS) + r")\s+"
    r"(day|week|fortnight|month|quarter|year)s?\b",
    re.I,
)

# "by the end of next quarter", "before the year is out"
DEADLINE = re.compile(
    r"\b(?:by|before)\s+(?:the\s+)?(?:end\s+of\s+)?"
    r"(?:this|next|the\s+coming)?\s*"
    r"(day|week|month|quarter|year|spring|summer|fall|autumn|winter)\b",
    re.I,
)

# Modals that commit rather than speculate.
COMMIT = re.compile(r"\b(will|shall|must|is going to|are going to)\b", re.I)
# Modals that hedge.
HEDGE = re.compile(r"\b(may|might|could|would|should|perhaps|possibly)\b", re.I)

SEASON_DAYS = {
    "spring": 120, "summer": 210, "fall": 300, "autumn": 300, "winter": 60,
}


@dataclass(frozen=True)
class Horizon:
    text: str
    days: int
    kind: str          # "duration" | "deadline"
    start: int
    end: int


def _to_days(count: str, unit: str) -> int:
    n = int(count) if count.isdigit() else NUMWORDS.get(count.lower(), 1)
    return n * UNIT_DAYS[unit.lower()]


def extract(text: str) -> list[Horizon]:
    """Every forward horizon in `text`, in order of appearance."""
    out: list[Horizon] = []
    for m in DURATION.finditer(text):
        out.append(Horizon(m.group(0), _to_days(m.group(1), m.group(2)),
                           "duration", m.start(), m.end()))
    for m in DEADLINE.finditer(text):
        unit = m.group(1).lower()
        days = SEASON_DAYS.get(unit, UNIT_DAYS.get(unit, 0))
        out.append(Horizon(m.group(0), days, "deadline", m.start(), m.end()))
    return sorted(out, key=lambda h: h.start)


def bucket(days: int) -> str:
    """Coarse proximity band. The 91-180 band is the six-month window."""
    if days <= 30:
        return "0-30d"
    if days <= 90:
        return "31-90d"
    if days <= 180:
        return "91-180d"
    if days <= 365:
        return "181-365d"
    return ">365d"


def commit_ratio(text: str) -> float:
    """Committing modals over committing-plus-hedging. 1.0 = no hedging."""
    c = len(COMMIT.findall(text))
    h = len(HEDGE.findall(text))
    return c / (c + h) if (c + h) else 0.0
