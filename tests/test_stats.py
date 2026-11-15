from datetime import date

from prs import corpus, stats


def _s(sid, d, text):
    return corpus.Speech(id=sid, date=date(*d), text=text)


def test_aggregate_groups_by_era():
    speeches = [
        _s("a", (1933, 3, 12), "We will act within six months."),
        _s("b", (1961, 1, 20), "We shall pay any price."),
    ]
    agg = corpus.aggregate(speeches)
    assert "pre_tv" in agg
    assert "tv_early" in agg


def test_lag_analysis():
    speeches = [_s("a", (1933, 3, 12), "We will act within six months.")]
    actions = {"a": "1933-03-16"}
    lag = stats.lag_analysis(speeches, actions)
    assert lag["30d"]["n_with_action"] == 1
