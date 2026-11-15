"""Era segmentation, keyed to the broadcast medium a speech was written for."""

from datetime import date

# Boundaries are approximate on purpose; they mark when the medium changed,
# not a clean cut in the rhetoric.
ERAS = [
    ("pre_tv",    None,               date(1947, 10, 5), "print and radio"),
    ("tv_early",  date(1947, 10, 5),  date(1963, 11, 22), "black-and-white TV"),
    ("tv_color",  date(1963, 11, 22), date(1980, 6, 1),   "color TV, three networks"),
    ("cable",     date(1980, 6, 1),   date(2007, 1, 9),   "cable, fragmented audience"),
    ("internet",  date(2007, 1, 9),   None,               "social, clip-length"),
]


def classify(d: date) -> str:
    for name, start, end, _ in ERAS:
        if (start is None or d >= start) and (end is None or d < end):
            return name
    return "unknown"


def describe(name: str) -> str:
    for n, _, _, note in ERAS:
        if n == name:
            return note
    return ""
