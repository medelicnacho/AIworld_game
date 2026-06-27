"""Prajñā tests (deterministic): wisdom loosens the grip at its source and unveils the
ground -- the two wings -- and is off by default; the prompt carries the nihilism guard."""

from agent.agent import Agent
from agent.memory import Memory
from agent import manas
from services import embed
from services.llm import MockLLM, SpeechContext, build_system


def _agent(grip=0.0, prajna=0.0, ground=False, temp=0.0):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1, temperament=temp)
    a.grip, a.prajna, a.ground_enabled = grip, prajna, ground
    return a


def test_prajna_off_by_default():
    assert _agent().prajna == 0.0


def test_effective_grip_loosened_by_wisdom():
    a = _agent(grip=1.0, prajna=0.75)
    assert abs(a.effective_grip() - 0.25) < 1e-9     # grip * (1 - prajna)


def test_wing1_wisdom_loosens_clinging():
    # the grip amplifies an aversive self-memory; prajñā gives it less to clutch
    embed.use_jaccard_only(True)
    try:
        def amplified(prajna):
            a = _agent(grip=1.0, prajna=prajna)
            m = Memory("my loss and my grief", 0.6, 0, 0, source="self", emotion=-0.5)
            a.memory.items = [m]
            manas.apply(a, now=1)
            return m.emotion
        assert amplified(0.8) > amplified(0.0)        # less negative = clung to less
    finally:
        embed.use_jaccard_only(False)


def test_wing2_wisdom_unveils_warmth():
    # under the grip the ground is veiled; prajñā lets it show -> felt mood rises
    veiled = _agent(grip=1.0, prajna=0.0, ground=True).felt_mood()
    seen = _agent(grip=1.0, prajna=0.8, ground=True).felt_mood()
    assert seen > veiled


def test_prajna_prompt_carries_nihilism_guard():
    sysp = build_system(SpeechContext(name="S", persona="p", mood=0.0, prajna=0.8))
    assert "empty" in sysp.lower()
    assert "nothing matters" in sysp.lower()          # the guard is explicit
    plain = build_system(SpeechContext(name="S", persona="p", mood=0.0, prajna=0.0))
    assert "passing configurations" not in plain
