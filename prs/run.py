"""End-to-end pipeline.

    python -m prs.run --corpus speeches.jsonl --out ./analysis
    python -m prs.run --dir ./speeches --actions actions.json --out ./analysis
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import corpus as C
from . import essay, report, segments, stats


def _write_csv(profiles: list[dict], path: Path) -> None:
    if not profiles:
        path.write_text("", encoding="utf-8")
        return
    fields = ["id", "date", "era", "words", "sentences", "horizons",
              "six_month", "commit_ratio"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in profiles:
            w.writerow(row)


def build(corpus_path: str | None,
          dir_path: str | None,
          actions_path: str | None = None,
          presidents_path: str | None = None,
          out_dir: str = "analysis",
          curve_id: str | None = None) -> dict:
    if corpus_path:
        speeches = C.load(corpus_path)
    elif dir_path:
        speeches = C.load(dir_path)
    else:
        raise ValueError("one of corpus_path or dir_path is required")

    if not speeches:
        raise ValueError("no speeches loaded")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    actions = None
    if actions_path:
        with open(actions_path, encoding="utf-8") as fh:
            actions = json.load(fh)

    presidents = None
    if presidents_path:
        with open(presidents_path, encoding="utf-8") as fh:
            presidents = json.load(fh)

    profiles = C.profile_corpus(speeches)
    by_era = C.aggregate(speeches)
    by_year = C.aggregate_by_year(speeches)

    result: dict = {
        "corpus": {
            "speeches": len(speeches),
            "words": sum(s.word_count() for s in speeches),
            "first": min(s.date for s in speeches).isoformat(),
            "last": max(s.date for s in speeches).isoformat(),
        },
        "eras": by_era,
        "years": {str(y): v for y, v in by_year.items()},
        "features": stats.feature_summary(speeches),
    }

    if presidents:
        result["presidents"] = C.aggregate_by_president(speeches, presidents)

    if actions:
        result["lag"] = stats.lag_analysis(speeches, actions)

    if curve_id:
        target = next((s for s in speeches if s.id == curve_id), None)
        if target is not None:
            result["curve"] = {
                "id": curve_id,
                "points": segments.curve(target),
            }

    (out / "summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    (out / "eras.json").write_text(
        json.dumps(by_era, indent=2), encoding="utf-8")
    (out / "years.json").write_text(
        json.dumps({str(y): v for y, v in by_year.items()}, indent=2),
        encoding="utf-8")
    if actions:
        (out / "lag.json").write_text(
            json.dumps(result["lag"], indent=2), encoding="utf-8")

    _write_csv(profiles, out / "profiles.csv")
    (out / "report.md").write_text(
        report.to_markdown(result), encoding="utf-8")
    essay.write(result, str(out / "essay.md"))

    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="prs.run")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--corpus", help="JSONL or JSON file of speeches")
    src.add_argument("--dir", help="directory of YYYY-MM-DD_*.txt files")
    p.add_argument("--actions", help="JSON: speech id -> action date")
    p.add_argument("--presidents", help="JSON: speech id -> president name")
    p.add_argument("--curve", help="speech id to trace passage-by-passage")
    p.add_argument("--out", default="analysis", help="output directory")
    a = p.parse_args(argv)

    try:
        result = build(a.corpus, a.dir, a.actions, a.presidents,
                       a.out, a.curve)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    c = result["corpus"]
    print(f"loaded {c['speeches']} speeches, {c['words']:,} words")
    print(f"range {c['first']} to {c['last']}")
    print(f"eras: {', '.join(result['eras'])}")
    if "lag" in result:
        print("lag: written")
    print(f"wrote {a.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
