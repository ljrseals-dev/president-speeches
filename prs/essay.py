"""Render the analysis as a markdown document with measured claims.

The essay's empirical sections are filled from a result dict rather than
asserted. Sections with no supporting data say so explicitly.
"""

from __future__ import annotations

BAND_ORDER = ["0-30d", "31-90d", "91-180d", "181-365d", ">365d"]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _era_table(eras: dict) -> str:
    if not eras:
        return "_No era data._\n"
    lines = ["| era | speeches | words | horizons/1k words | "
             "91-180d share | commit ratio |",
             "|---|---:|---:|---:|---:|---:|"]
    for era, d in eras.items():
        share = d["band_share"].get("91-180d", 0.0)
        lines.append(
            f"| {era} | {d['speeches']} | {d.get('words', 0):,} | "
            f"{d.get('per_1k_words', 0)} | {_pct(share)} | "
            f"{d['mean_commit_ratio']} |"
        )
    return "\n".join(lines) + "\n"


def _lag_table(lag: dict) -> str:
    if not lag:
        return ("_No action dates supplied. The lag analysis needs a "
                "speech-id to action-date mapping; without it this section "
                "reports method only._\n")
    lines = ["| window | n with action | n without | mean 91-180d (with) | "
             "mean 91-180d (without) |",
             "|---|---:|---:|---:|---:|"]
    for w, d in lag.items():
        lines.append(
            f"| {w} | {d['n_with_action']} | {d['n_without']} | "
            f"{d['mean_six_month_with']} | {d['mean_six_month_without']} |"
        )
    return "\n".join(lines) + "\n"


def _feature_table(feats: dict) -> str:
    if not feats:
        return "_No feature data._\n"
    lines = ["| feature | mean | stdev | min | max |",
             "|---|---:|---:|---:|---:|"]
    for name, d in feats.items():
        if "min" in d:
            lines.append(f"| {name} | {d['mean']} | {d['stdev']} | "
                         f"{d['min']} | {d['max']} |")
    return "\n".join(lines) + "\n"


def render(result: dict) -> str:
    c = result["corpus"]
    eras = result.get("eras", {})
    lag = result.get("lag")

    out = [
        "# Presidential speech: measured analysis",
        "",
        f"Corpus of **{c['speeches']} speeches**, {c['words']:,} words, "
        f"spanning {c['first']} to {c['last']}.",
        "",
        "## Temporal framing by era",
        "",
        "Forward-looking expressions are extracted, converted to a "
        "day-count, and bucketed. The 91-180 day band is the six-month "
        "window under test.",
        "",
        _era_table(eras),
        "## Lag analysis",
        "",
        _lag_table(lag),
        "## Rhetorical features",
        "",
        _feature_table(result.get("features", {})),
        "## Method",
        "",
        "All figures are computed by counting: horizon expressions matched "
        "by pattern and converted to days, modals counted and classified, "
        "sentences split on terminal punctuation with abbreviation "
        "protection. No language model contributes to any number reported "
        "here. The instrument measures a corpus; it does not generate or "
        "optimize speech.",
        "",
    ]
    return "\n".join(out)


def write(result: dict, path: str) -> None:
    from pathlib import Path
    Path(path).write_text(render(result), encoding="utf-8")
