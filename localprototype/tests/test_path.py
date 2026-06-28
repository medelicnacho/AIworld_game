"""The Path (bhāvanā) tests -- deterministic: recent practice grooves the faculties.

The driving signal is the EQUANIMITY a reflection was written with (its memory.emotion),
so these inject reflection memories with known emotion and check the faculty drift; no LLM."""

from agent import path
from agent.agent import Agent
from services.llm import MockLLM


def _soul(grip=0.6, prajna=0.2):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.grip, a.prajna = grip, prajna
    a.cultivate_enabled = True
    return a


def _reflect_mem(a, emotion, now=5):
    # genuinely low-overlap text -- memory merges entries with >=0.6 word overlap (real
    # reflections are varied; identical/similar test text would collapse to one memory)
    a.memory.write(f"reflection {now} unique {now * 7} marker {now * 13} note",
                   tick=now, source="reflection", speaker_id="s", emotion=emotion, weight=1.0)


def test_no_reflection_no_cultivation():
    a = _soul()
    g0, p0 = a.grip, a.prajna
    path.cultivate(a, now=5)
    assert a.grip == g0 and a.prajna == p0      # the path is walked, not declared


def test_equanimous_practice_frees():
    a = _soul(grip=0.6, prajna=0.2)
    _reflect_mem(a, emotion=+0.6, now=5)
    path.cultivate(a, now=5)
    assert a.grip < 0.6        # the grip loosens
    assert a.prajna > 0.2      # wisdom grows


def test_rumination_grooves_the_grip():
    a = _soul(grip=0.4, prajna=0.3)
    _reflect_mem(a, emotion=-0.6, now=5)
    p0 = a.prajna
    path.cultivate(a, now=5)
    assert a.grip > 0.4        # clinging deepens
    assert a.prajna == p0      # rumination doesn't grow wisdom


def test_only_recent_practice_counts():
    a = _soul(grip=0.6)
    _reflect_mem(a, emotion=+0.6, now=1)        # long ago, outside the window
    g0 = a.grip
    path.cultivate(a, now=1 + path.WINDOW + 5)
    assert a.grip == g0                          # stale practice doesn't cultivate


def test_faculties_stay_bounded():
    a = _soul(grip=0.01, prajna=0.99)
    for t in range(1, 60):
        _reflect_mem(a, emotion=+0.8, now=t)
        path.cultivate(a, now=t)
    assert 0.0 <= a.grip <= 1.0 and 0.0 <= a.prajna <= 1.0


def test_a_life_of_practice_drifts_toward_freedom():
    # a soul that starts clinging, meeting its mind with equanimity over a long life
    a = _soul(grip=0.7, prajna=0.1)
    for t in range(1, 80):
        _reflect_mem(a, emotion=+0.5, now=t)
        path.cultivate(a, now=t)
    assert a.grip < 0.3 and a.prajna > 0.4       # remade by practice
