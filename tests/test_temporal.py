from prs import temporal


def test_duration_extraction():
    hs = temporal.extract("We will act within six months.")
    assert len(hs) == 1
    assert hs[0].days == 180
    assert hs[0].kind == "duration"


def test_deadline_extraction():
    hs = temporal.extract("By the end of next quarter we will know.")
    assert any(h.kind == "deadline" for h in hs)


def test_bucket_boundaries():
    assert temporal.bucket(30) == "0-30d"
    assert temporal.bucket(91) == "91-180d"
    assert temporal.bucket(180) == "91-180d"
    assert temporal.bucket(181) == "181-365d"
    assert temporal.bucket(400) == ">365d"


def test_commit_ratio():
    assert temporal.commit_ratio("We will act.") == 1.0
    assert temporal.commit_ratio("We may act.") == 0.0
    assert 0 < temporal.commit_ratio("We will act, though we might wait.") < 1
