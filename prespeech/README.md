# prespeech

Compatibility alias for **prs**.

All implementation lives in the `prs` package. Importing from `prespeech`
is identical to importing from `prs`:

```python
from prespeech import corpus, stats, report
# same as
from prs import corpus, stats, report
```

```bash
python -m prespeech.cli report --corpus speeches.jsonl
# same as
python -m prs.cli report --corpus speeches.jsonl
```
