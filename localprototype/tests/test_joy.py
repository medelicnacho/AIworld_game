"""Joy (savouring) tests -- deterministic. Savouring holds pleasant charges so the good
lasts; the near-enemy craving (a clutching grip without joy/transmute) drains the sweetness.

Jaccard forced so manas.relevance_of is source-based (self-statements are self-relevant),
keeping the craving path deterministic without Ollama."""

import pytest

from agent import joy, manas
from agent.agent import Agent
from services import embed
from services.llm import MockLLM


@pytest.fixture(autouse=True)
def _jaccard():
    embed.use_jaccard_only(True)
    yield
    embed.use_jaccard_only(False)


def _soul(joy_=0.0, grip=0.0, prajna=0.0, transmute=0.0):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.joy, a.grip, a.prajna, a.transmute = joy_, grip, prajna, transmute
    return a


def _good(a, emotion=0.8, now=5):
    a.memory.write("a good thing happened to me", tick=now, source="self",
                   speaker_id="s", emotion=emotion, weight=1.0)
    return next(m for m in a.memory.items if "good thing" in m.text)


def test_joy_off_is_noop():
    a = _soul(joy_=0.0)
    m = _good(a)
    s0 = m.salience
    joy.apply(a, now=5)
    assert m.salience == s0            # anhedonic default: the good is not savoured


def test_savouring_holds_the_good():
    a = _soul(joy_=0.6)
    m = _good(a)
    s0, e0 = m.salience, m.emotion
    joy.apply(a, now=5)
    assert m.salience > s0             # dwelt in -> it lasts (lifts mood, which is salience-weighted)
    assert m.emotion == e0            # received as it is, NOT amplified into wanting-more


def test_savouring_ignores_aversive():
    a = _soul(joy_=0.6)
    a.memory.write("a bad thing", tick=5, source="self", speaker_id="s", emotion=-0.8)
    bad = next(m for m in a.memory.items if m.text == "a bad thing")
    s0 = bad.salience
    joy.apply(a, now=5)
    assert bad.salience == s0          # joy savours the good; it does not touch pain


def test_craving_drains_the_sweetness():
    # a clutching grip, no joy and no transmutation -> raga: the good is held but drained
    a = _soul(grip=0.9)
    m = _good(a, emotion=0.8)
    e0 = m.emotion
    manas.apply(a, now=5)
    assert m.emotion < e0             # the treadmill: clutching pleasure drains it
    assert m.emotion > 0.0           # still pleasant, just lessened


def test_joy_spares_the_good_from_craving():
    # with joy on, the same gripping soul SAVOURS instead of craving -> the good is not drained
    a = _soul(joy_=0.6, grip=0.9)
    m = _good(a, emotion=0.8)
    e0 = m.emotion
    manas.apply(a, now=5)
    assert m.emotion == e0           # joy present -> manas does not drain the pleasant charge


def test_savouring_stays_bounded():
    a = _soul(joy_=1.0)
    m = _good(a, emotion=0.9)
    for t in range(40):
        joy.apply(a, now=5)
    assert m.salience <= 1.0


def test_mudita_turn_prompt():
    from services.llm import SpeechContext, build_user
    out = build_user(SpeechContext(name="B", persona="p", mood=0.0,
                                   mudita_turn=True, reply_to_name="Ada", concept_mind=True))
    assert "glad for" in out and "Ada" in out          # rejoice WITH them (overrides voice mode)
    assert "share their joy" in out


def test_liberated_and_joyful_savour():
    from agent import archetype as arch
    a = Agent("x", "X", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    arch.apply(a, arch.LIBERATED)
    assert a.joy >= 0.8                                  # the liberated self can have good days
    assert arch.BY_NAME["Joyful"].joy >= 0.8
    assert arch.BY_NAME["Grasper"].joy == 0.0           # the grasper does not savour
