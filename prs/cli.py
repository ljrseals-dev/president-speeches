"""Command line entry point.

    python -m prs.cli report --corpus speeches.jsonl
    python -m prs.cli report --dir ./speeches --actions actions.json
    python -m prs.cli curve --corpus speeches.jsonl --id fdr-1933-03-12
"""

import argparse
import json
import sys

from . import corpus, report, segments, stats


def _load(a) -> list[corpus.Speech]:
    return (corpus.load_jsonl(a.corpus) if a.corpus
            else corpus.load_dir(a.dir))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="prs")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("report", help="analyze a corpus and print markdown")
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--corpus", help="JSONL file of speech records")
    src.add_argument("--dir", help="directory of YYYY-MM-DD_*.txt files")
    r.add_argument("--actions", help="JSON file mapping speech id -> action date")
    r.add_argument("--json", action="store_true", help="emit raw JSON instead")

    c = sub.add_parser("curve", help="horizon shape across one speech")
    csrc = c.add_mutually_exclusive_group(required=True)
    csrc.add_argument("--corpus", help="JSONL file of speech records")
    csrc.add_argument("--dir", help="directory of YYYY-MM-DD_*.txt files")
    c.add_argument("--id", required=True, help="speech id to trace")
    c.add_argument("--window", type=int, default=5, help="sentences per window")

    a = p.parse_args(argv)

    if a.cmd == "report":
        speeches = _load(a)
        if not speeches:
            print("no speeches loaded", file=sys.stderr)
            return 1
        actions = None
        if a.actions:
            with open(a.actions, encoding="utf-8") as fh:
                actions = json.load(fh)
        rep = stats.full_report(speeches, actions)
        print(json.dumps(rep, indent=2) if a.json
              else report.to_markdown(rep))
        return 0

    if a.cmd == "curve":
        speeches = _load(a)
        target = next((s for s in speeches if s.id == a.id), None)
        if target is None:
            print(f"no speech with id {a.id!r}", file=sys.stderr)
            return 1
        for row in segments.curve(target, a.window):
            print(json.dumps(row))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
