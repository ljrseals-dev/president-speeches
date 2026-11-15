"""prs — analysis of presidential speech corpora.

An analysis instrument. It measures patterns in a corpus; it does not
generate or optimize speech drafts.

    from prs import corpus, stats, report, moral

    speeches = corpus.load_jsonl("speeches.jsonl")
    print(report.to_markdown(stats.full_report(speeches)))
"""

from . import corpus, eras, features, report, stats, temporal
from . import moral, segments, synthetic, essay, run

__version__ = "0.2.0"
__all__ = [
    "corpus", "eras", "features", "stats", "report", "temporal",
    "moral", "segments", "synthetic", "essay", "run",
]
