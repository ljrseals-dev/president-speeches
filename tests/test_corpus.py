from datetime import date

from prs import corpus, features


def _speech(text="We will act within six months. We will act. We will act."):
    return corpus.Speech(id="t1", date=date(1933, 3, 12), text=text)


def test_era_assignment():
    assert _speech().era == "pre_tv"
    s = corpus.Speech(id="t2", date=date(1961, 1, 20), text="x")
    assert s.era == "tv_early"


def test_horizon_profile():
    p = corpus.horizon_profile(_speech())
    assert p["six_month"] == 1
    assert p["commit_ratio"] == 1.0


def test_anaphora_detection():
    f = features.extract(_speech())
    assert f.anaphora_runs >= 1


def test_split_sentences_abbreviation():
    sents = corpus.split_sentences(
        "Mr. Smith went to Washington. He will act within six months."
    )
    assert len(sents) == 2
    assert "Mr. Smith" in sents[0]
