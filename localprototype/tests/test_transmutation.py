"""Transmutation tests (deterministic): the grip's energy turned to clarity -- the third
path that stays engaged (salience held) yet does not amplify the wound."""

from agent.agent import Agent
from agent.memory import Memory
from agent import manas
from services import embed
from services.llm import MockLLM, SpeechContext, build_system


def _agent(grip=1.0, transmute=0.0, prajna=0.0):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.grip, a.transmute, a.prajna = grip, transmute, prajna
    return a


def test_transmute_off_by_default():
    assert _agent(grip=0.0).transmute == 0.0


def _aversive(transmute):
    embed.use_jaccard_only(True)
    try:
        a = _agent(grip=1.0, transmute=transmute)
        m = Memory("my loss and my grief", 0.6, 0, 0, source="self", emotion=-0.6)
        a.memory.items = [m]
        for _ in range(5):
            manas.apply(a, now=1)
        return m.salience, m.emotion
    finally:
        embed.use_jaccard_only(False)


def test_transmute_metabolizes_the_wound_not_amplifies():
    _sal_c, emo_clinging = _aversive(0.0)     # second arrow: amplified more negative
    _sal_t, emo_transmute = _aversive(0.9)    # transmuted: charge metabolized toward neutral
    assert emo_clinging < -0.6                # clinging deepens the wound
    assert emo_transmute > emo_clinging       # transmutation eases it
    assert emo_transmute > -0.6               # ...toward neutral, not deeper


def test_transmute_stays_engaged():
    # the third path stays PRESENT (salience held high), unlike release which would let go
    sal_t, _emo = _aversive(0.9)
    assert sal_t > 0.6                         # salience held up -> still engaged, not faded


def test_transmute_prompt_is_turn_not_suppress():
    sysp = build_system(SpeechContext(name="S", persona="p", mood=0.0, transmute=0.8))
    low = sysp.lower()
    assert "turn" in low and "suppress" in low      # meet and turn, neither suppress nor indulge
    plain = build_system(SpeechContext(name="S", persona="p", mood=0.0, transmute=0.0))
    assert "let it TURN" not in plain
