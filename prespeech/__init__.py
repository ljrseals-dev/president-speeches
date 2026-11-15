"""prespeech — compatibility alias for prs.

All analysis lives in the `prs` package. This module re-exports the same
API so existing imports of the form `from prespeech import ...` continue
to work.

    from prespeech import corpus, stats, report
    # identical to:
    from prs import corpus, stats, report
"""

from prs import corpus, eras, features, report, segments, stats, temporal
from prs import __version__

__all__ = ["corpus", "eras", "features", "stats", "report", "temporal", "segments"]
