# prs / prespeech

Analysis of presidential speech corpora.

**Canonical package:** `prs`  
**Alias:** `prespeech` (re-exports everything from `prs`)

## What it does

- **Era segmentation** — pre-TV, black-and-white TV, color TV, cable, internet
- **Temporal framing** — forward-looking expressions → day-count → proximity bands (including the six-month window)
- **Commitment vs. hedging** — committing modals over committing-plus-hedging
- **Rhetorical features** — anaphora, tricolon, pronoun share, direct address, sentence length, type-token ratio
- **Lag analysis** — six-month horizon density vs. later formal action
- **Passage shape** — `segments.curve()` traces commitments across a speech

## Install

No external dependencies. Python 3.10+.

```bash
pip install dist/prs-0.2.0-py3-none-any.whl
# or
PYTHONPATH=. python -c "from prs import temporal"
```

## Usage

```python
from prs import corpus, stats, report          # preferred
from prespeech import corpus, stats, report    # identical alias

speeches = corpus.load_jsonl("speeches.jsonl")
print(report.to_markdown(stats.full_report(speeches)))
```

```bash
python -m prs.cli report --corpus speeches.jsonl
python -m prespeech.cli report --corpus speeches.jsonl   # same
python -m prs.cli curve --corpus speeches.jsonl --id fdr-1933-03-12
```

## Layout

```
prs/                 # implementation
  corpus.py
  eras.py
  temporal.py
  features.py
  segments.py
  stats.py
  report.py
  cli.py
prespeech/           # thin re-export alias
tests/
```
