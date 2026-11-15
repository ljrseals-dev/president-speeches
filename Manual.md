# prs / prespeech — Technical Manual

**Version:** 0.1.0  
**Python:** 3.10+  
**Dependencies:** none

---

## 1. Purpose

`prs` (alias `prespeech`) is a deterministic analysis instrument for presidential speech corpora. It measures:

- Where forward-looking language points in time (horizon extraction → day-counts → proximity bands)
- How much of that language lands in the six-month window (`91-180d`)
- Commitment vs. hedging (modal ratio)
- Classical rhetorical features (anaphora, tricolon, pronoun share, address, sentence length, TTR)
- Whether six-month horizon density correlates with later formal action (lag analysis)
- The shape of commitments across a single speech (passage curves)

It does **not** generate or optimize speech drafts. Metaphor-domain tagging (which would need a language model) is deliberately excluded from the measurement path so all numbers remain auditable.

---

## 2. Package layout

```
prs/                 # canonical implementation
  __init__.py
  corpus.py          # load, normalise, Speech, profiles, aggregate
  eras.py            # broadcast-era boundaries
  temporal.py        # horizon extraction, bucket, commit_ratio
  features.py        # rhetorical / lexical features
  segments.py        # sliding-window passage shape
  stats.py           # feature_summary, lag_analysis, full_report
  report.py          # markdown renderer
  cli.py             # command-line entry

prespeech/           # thin re-export alias (identical API)
tests/
  test_temporal.py
  test_corpus.py
  test_stats.py
Manual.md            # this file
README.md
pyproject.toml
setup.py
setup.cfg
```

Import either name; both resolve to the same objects:

```python
from prs import temporal as t1
from prespeech import temporal as t2
assert t1.extract is t2.extract
```

---

## 3. Install / run

```bash
# from source tree
PYTHONPATH=. python -c "from prs import temporal; print(temporal.extract('We will act within six months.'))"

# CLI
python -m prs.cli report --corpus speeches.jsonl
python -m prespeech.cli report --corpus speeches.jsonl   # same

# tests
PYTHONPATH=. python -m pytest tests/ -v
```

Optional wheel / editable install when a build tool is available:

```bash
pip install dist/prs-0.1.0-py3-none-any.whl
# or
pip install -e .
```

---

## 4. Corpus formats

### JSONL (preferred)

One JSON object per line:

```json
{"id": "fdr-1933-03-12", "date": "1933-03-12", "title": "First Fireside Chat", "text": "..."}
```

Accepted keys for text: `text`, `transcript`, `body`  
Accepted keys for date: `date`, `delivered`, `when`

### Directory of `.txt` files

Files named `YYYY-MM-DD_rest.txt` take the date from the filename.  
Files without a date prefix are scanned for an ISO date in the first few lines.

### JSON array / object

`load_json` accepts a list of records or an object with a `speeches` / `records` / `documents` / `items` list.

Malformed lines or records are skipped; a partially corrupt export still yields the intact speeches.

---

## 5. Core modules

### 5.1 `temporal` — horizon extraction

| Function | Role |
|----------|------|
| `extract(text)` | Returns `list[Horizon]` — every duration/deadline expression |
| `bucket(days)` | Maps day-count → `"0-30d"` \| `"31-90d"` \| `"91-180d"` \| `"181-365d"` \| `">365d"` |
| `commit_ratio(text)` | Committing modals / (committing + hedging); 1.0 = no hedge |

Patterns covered:

- Durations: `within six months`, `in the next 90 days`, `over the coming weeks`
- Deadlines: `by the end of next quarter`, `before the year is out`, seasons
- Modals: will / shall / must / is going to  vs  may / might / could / would / should / perhaps / possibly

The **six-month hypothesis** lives in the `91-180d` band (`bucket(180) == "91-180d"`).

### 5.2 `eras` — broadcast medium

| Era | Approximate start | Note |
|-----|-------------------|------|
| `pre_tv` | — | print and radio |
| `tv_early` | 1947-10-05 | black-and-white TV |
| `tv_color` | 1963-11-22 | color TV, three networks |
| `cable` | 1980-06-01 | cable, fragmented audience |
| `internet` | 2007-01-09 | social, clip-length |

Boundaries mark medium change, not a clean cut in rhetoric.

### 5.3 `corpus` — load, normalise, profile, aggregate

- **Normalisation:** NFKC, Unicode punctuation map, strip speaker labels and stage directions (`[laughter]`, `(applause)`, …), collapse whitespace while keeping paragraph breaks. Lossless w.r.t. words spoken.
- **Sentence splitter:** abbreviation-aware (Mr., U.S., etc.) and single-initial aware; conservative by design.
- **`Speech`:** `id`, `date`, `text`, `title`, `source`, auto-assigned `era`.
- **`horizon_profile(speech)`:** per-speech bands, six-month count, commit ratio, word/sentence counts.
- **`aggregate(speeches)`:** per-era totals, per-speech rate, per-1k-words rate, band shares, mean commit ratio.
- Also: `aggregate_by_year`, `aggregate_by_president`, `Corpus` wrapper with `filter` / `profiles` / `by_era` / `by_year`.

### 5.4 `features` — rhetorical layer

| Feature | Description |
|---------|-------------|
| `mean_sentence_len` / `sentence_len_stdev` | Length distribution |
| `anaphora_runs` | Runs of 3+ consecutive sentences sharing an opening word |
| `tricolon_count` | Parallel three-item constructions |
| `pronoun_share` | `we` / `i` / `you` rates |
| `address_count` | Direct address (“my friends”, “fellow Americans”, “let us”, …) |
| `type_token_ratio` | Lexical diversity |

All regex/count based; no model.

### 5.5 `segments` — passage shape

`segments.curve(speech, window=5)` slides overlapping windows of sentences and returns, for each position:

```json
{"index": 0, "six_month": 1, "horizons": 2, "commit_ratio": 1.0}
```

Use to see where commitments concentrate from opening to close.

### 5.6 `stats` + `report`

- `feature_summary(speeches)` — mean / stdev / min / max for each feature
- `lag_analysis(speeches, actions)` — mean six-month horizon count for speeches followed by action inside 30/90/180/365 days vs. those not
- `full_report(speeches, actions=None)` — eras + features + optional lag
- `report.to_markdown(rep)` — printable tables

`actions` is a dict `{speech_id: "YYYY-MM-DD"}` of the formal action that followed.

---

## 6. CLI

```bash
python -m prs.cli report --corpus speeches.jsonl
python -m prs.cli report --dir ./speeches --actions actions.json
python -m prs.cli report --corpus speeches.jsonl --json
python -m prs.cli curve  --corpus speeches.jsonl --id fdr-1933-03-12 --window 5
```

`prespeech.cli` is an identical entry point.

---

## 7. Library example

```python
from prs import corpus, stats, report, segments

speeches = corpus.load_jsonl("speeches.jsonl")
rep = stats.full_report(speeches, actions={"fdr-1933-03-12": "1933-03-16"})
print(report.to_markdown(rep))

for row in segments.curve(speeches[0]):
    print(row)
```

---

## 8. Design constraints (intentional)

1. **No network, no models** in the measurement path — every number is reproducible from text + regex + counts.
2. **Conservative sentence splitting** — over-splitting would corrupt every length statistic.
3. **Six-month band is explicit** — `91-180d` is the hypothesis window; it is not hidden inside a continuous score.
4. **Alias, not fork** — `prespeech` re-exports `prs`; there is one implementation.

---

## 9. Sanity checks

```bash
PYTHONPATH=. python -c "
from prs import temporal, corpus
print(temporal.extract('We will act within six months.'))
print(corpus.split_sentences('Mr. Smith went to Washington. He will act within six months.'))
"
```

Expected:

```
[Horizon(text='within six months', days=180, kind='duration', ...)]
['Mr. Smith went to Washington.', 'He will act within six months.']
```

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

All tests should pass.

---

*End of manual.*

---

## 10. Moral-language analyzer (`prs.moral`)

Descriptive measurement of Moral Foundations vocabulary.

- **Seed lexicon** (care, fairness, loyalty, authority, sanctity × virtue/vice)
- **Negation**: clause-bounded two-token window; negated hits excluded and reported separately
- **MFD 2.0**: `load_mfd(path)` for a JSON lexicon file
- **No verdict**: counts and shares only; no morality score, no ranking

```python
from prs import moral
r = moral.analyze(text)
print(r.summary())
# negated hits visible in r.negated_hits
```

## 11. Pipeline (`prs.run`)

```bash
python -m prs.run --corpus speeches.jsonl --actions actions.json --out ./analysis
```

Writes: `summary.json`, `eras.json`, `years.json`, `lag.json`, `profiles.csv`, `report.md`, `essay.md`.

## 12. Synthetic validation (`prs.synthetic`)

```python
from prs import synthetic
s = synthetic.generate(300)
synthetic.write_jsonl(s, "syn.jsonl")
synthetic.write_actions(s, "syn_actions.json")
```

## 13. Documents

- `documents/The_Hidden_Grammar_of_Presidential_Speech.md` — theoretical essay (classical, fireside, television, esoteric, empirical traditions)
