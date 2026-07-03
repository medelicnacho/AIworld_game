"""Tests for the drift monitor (services/drift.py, METHODS D1).

The validation criterion is the spec's own: the monitor must FIRE on an induced drift and
STAY QUIET across seed-only variation. Pinned here: warmup makes no verdicts (and no
silent states), a stable stream never warns, an induced mean-shift warns only after the
debounce streak (one hot check is weather), a vocabulary slide warns, the
generic-assistant PULL axis warns on a rise (not an absolute level), and recovery resets
the streak."""

import random

from services.drift import GENERIC_ASSISTANT, DriftMonitor


def _mon(**kw):
    base = dict(baseline_n=20, recent_n=10, debounce=3)
    base.update(kw)
    return DriftMonitor(**base)


def test_warmup_makes_no_verdicts():
    m = _mon()
    for i in range(5):
        m.observe("mood", 0.1)
        m.observe_text("her", "the rain came early over the fields")
    assert m.check() == []
    assert m.reference_pull("her") is None      # warming up says None, never a number


def test_stable_stream_stays_quiet_across_seed_variation():
    for seed in (11, 12, 13):
        m = _mon()
        rng = random.Random(seed)
        words = ["rain", "fields", "bread", "river", "lamps", "harvest", "fence", "well"]
        for _ in range(120):
            m.observe("len", 40 + rng.random() * 4)
            m.observe_text("her", " ".join(rng.choice(words) for _ in range(6)))
            assert m.check() == []              # seed-only variation: silence


def test_induced_mean_shift_fires_after_debounce_only():
    m = _mon()
    rng = random.Random(7)
    for _ in range(30):
        m.observe("len", 40 + rng.random())     # baseline ~40
    fired_at = None
    for i in range(1, 7):
        m.observe("len", 80 + rng.random())     # the induced drift
        # keep the window fully shifted: recent_n=10, so push one more per check
        for _ in range(9):
            m.observe("len", 80 + rng.random())
        w = m.check()
        if w and fired_at is None:
            fired_at = i
    assert fired_at == 3                        # debounce: the third consecutive breach
    assert any(x.kind == "numeric" for x in m.check())


def test_recovery_resets_the_streak():
    m = _mon(debounce=2)
    rng = random.Random(7)
    for _ in range(30):
        m.observe("len", 40 + rng.random())
    for _ in range(10):
        m.observe("len", 80 + rng.random())
    assert m.check() == []                      # streak 1 of 2: weather, not drift yet
    for _ in range(10):
        m.observe("len", 40 + rng.random())     # it settles back
    assert m.check() == []                      # streak reset
    assert m._num["len"]["streak"] == 0


def test_vocabulary_slide_fires():
    m = _mon()
    old = ["rain", "fields", "bread", "river", "lamps", "harvest"]
    new = ["synergy", "paradigm", "leverage", "pipeline", "metrics", "roadmap"]
    rng = random.Random(3)
    for _ in range(20):
        m.observe_text("town", " ".join(rng.choice(old) for _ in range(6)))
    fired = False
    for _ in range(6):
        for _ in range(10):
            m.observe_text("town", " ".join(rng.choice(new) for _ in range(6)))
        if any(x.kind == "vocab" for x in m.check()):
            fired = True
            break
    assert fired


def test_generic_assistant_pull_fires_on_the_rise():
    m = _mon()
    rng = random.Random(5)
    plain = ["rain", "fields", "bread", "river", "lamps", "harvest"]
    assistant = sorted(GENERIC_ASSISTANT)
    for _ in range(20):
        m.observe_text("her", " ".join(rng.choice(plain) for _ in range(6)))
    m.check()                                   # establishes the pull baseline (~0)
    fired = False
    for _ in range(6):
        for _ in range(10):
            m.observe_text("her", " ".join(rng.choice(assistant) for _ in range(6)))
        if any(x.kind == "pull" for x in m.check()):
            fired = True
            break
    assert fired                                # the slide toward the assistant register
