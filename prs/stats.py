"""Corpus-level statistics.

Aggregates features and horizons across speeches, and does the
lag analysis: does language at time T predict formal action at T+N?
"""

from datetime import date as _date
from statistics import mean, pstdev

from . import features
from .corpus import Speech, aggregate, horizon_profile

FEATURE_FIELDS = [
    "mean_sentence_len", "sentence_len_stdev", "anaphora_runs",
    "tricolon_count", "address_count", "type_token_ratio",
]


def feature_summary(speeches: list[Speech]) -> dict:
    rows = [features.extract(s) for s in speeches]
    if not rows:
        return {}
    out: dict[str, dict] = {}
    for f in FEATURE_FIELDS:
        vals = [getattr(r, f) for r in rows]
        out[f] = {
            "mean": round(mean(vals), 3),
            "stdev": round(pstdev(vals), 3) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
        }
    for p in ("we", "i", "you"):
        vals = [r.pronoun_share[p] for r in rows]
        out[f"pronoun_{p}"] = {
            "mean": round(mean(vals), 4),
            "stdev": round(pstdev(vals), 4) if len(vals) > 1 else 0.0,
        }
    return out


def lag_analysis(speeches: list[Speech], actions: dict[str, str],
                 lags_days: tuple[int, ...] = (30, 90, 180, 365)) -> dict:
    """Correlate per-speech six-month horizon density with later action.

    `actions` maps speech id -> ISO date of the formal action that
    followed it. Speeches absent from `actions` are treated as having
    no following action (a negative example).

    Returns, per lag, the mean six-month horizon count for speeches
    with an action inside that window vs. those without.
    """
    profiles = {s.id: horizon_profile(s) for s in speeches}
    by_id = {s.id: s for s in speeches}
    out: dict[str, dict] = {}

    for lag in lags_days:
        hit: list[int] = []
        miss: list[int] = []
        for sid, prof in profiles.items():
            s = by_id[sid]
            act = actions.get(sid)
            if act:
                gap = (_date.fromisoformat(act) - s.date).days
                (hit if 0 <= gap <= lag else miss).append(prof["six_month"])
            else:
                miss.append(prof["six_month"])
        out[f"{lag}d"] = {
            "n_with_action": len(hit),
            "n_without": len(miss),
            "mean_six_month_with": round(mean(hit), 3) if hit else None,
            "mean_six_month_without": round(mean(miss), 3) if miss else None,
        }
    return out


def full_report(speeches: list[Speech],
                actions: dict[str, str] | None = None) -> dict:
    rep = {
        "eras": aggregate(speeches),
        "features": feature_summary(speeches),
    }
    if actions:
        rep["lag"] = lag_analysis(speeches, actions)
    return rep
