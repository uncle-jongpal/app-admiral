from admiral.ui.overlay import BARS, LevelTrack


def test_bars_follow_voice():
    t = LevelTrack()
    t.feed(0.0001)
    assert t.heights[-1] == 0.0
    t.feed(0.002)  # 작게 말해도 막대가 보임
    assert 0.2 < t.heights[-1] < 0.6
    t.feed(0.5)
    assert t.heights[-1] == 1.0
    assert len(t.heights) == BARS


def test_quiet_after_two_seconds():
    t = LevelTrack()
    t.feed(0.01)
    assert t.heard and not t.quiet
    for _ in range(39):
        t.feed(0.0002)
    assert not t.quiet
    t.feed(0.0002)
    assert t.quiet
    t.feed(0.01)
    assert not t.quiet
