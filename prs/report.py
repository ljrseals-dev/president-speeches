"""Render an analysis result as markdown."""

BAND_ORDER = ["0-30d", "31-90d", "91-180d", "181-365d", ">365d"]


def _band_row(share: dict) -> str:
    return " · ".join(f"{b} {share[b]:.0%}" for b in BAND_ORDER if b in share)


def to_markdown(rep: dict) -> str:
    lines = ["# Presidential speech analysis", ""]

    lines += ["## Temporal framing by era", "",
              "| era | speeches | horizons/speech | commit ratio | horizon bands |",
              "|---|---:|---:|---:|---|"]
    for era, d in rep.get("eras", {}).items():
        lines.append(f"| {era} | {d['speeches']} | {d['per_speech']} | "
                     f"{d['mean_commit_ratio']} | {_band_row(d['band_share'])} |")
    lines.append("")

    lines += ["## Rhetorical features", "",
              "| feature | mean | stdev | min | max |",
              "|---|---:|---:|---:|---:|"]
    for name, d in rep.get("features", {}).items():
        if "min" in d:
            lines.append(f"| {name} | {d['mean']} | {d['stdev']} | "
                         f"{d['min']} | {d['max']} |")
    lines.append("")

    feats = rep.get("features", {})
    for p in ("we", "i", "you"):
        k = f"pronoun_{p}"
        if k in feats:
            lines.append(f"- pronoun *{p}*: mean {feats[k]['mean']}, "
                         f"stdev {feats[k]['stdev']}")
    lines.append("")

    if "lag" in rep:
        lines += ["## Lag analysis", "",
                  "Mean six-month-horizon count, speeches followed by a formal "
                  "action inside the window vs. those not.", "",
                  "| window | n with action | n without | mean (with) | mean (without) |",
                  "|---|---:|---:|---:|---:|"]
        for w, d in rep["lag"].items():
            lines.append(f"| {w} | {d['n_with_action']} | {d['n_without']} | "
                         f"{d['mean_six_month_with']} | "
                         f"{d['mean_six_month_without']} |")
        lines.append("")
    return "\n".join(lines)
