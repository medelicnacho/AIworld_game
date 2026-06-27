"""Buddha-nature-as-ground tests (deterministic: felt_mood is pure math).

The ground lifts an UNOBSCURED soul's felt mood toward basic goodness; the grip veils
it; it's off by default so nothing existing changes."""

from agent.agent import Agent
from services.llm import MockLLM


def _agent(temp=0.0):
    return Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1, temperament=temp)


def test_ground_off_by_default():
    a = _agent()
    assert a.ground_enabled is False


def test_ground_lifts_felt_mood_when_unobscured():
    a = _agent(temp=0.0)
    off = a.felt_mood()
    a.ground_enabled = True
    on = a.felt_mood()
    assert on > off                 # basic goodness lifts the unobscured soul toward warmth


def test_grip_veils_the_ground():
    a = _agent(temp=0.0)
    a.ground_enabled = True
    a.grip = 0.0
    revealed = a.felt_mood()
    a.grip = 1.0
    veiled = a.felt_mood()
    assert revealed > veiled         # clinging obscures the ground


def test_ground_lifts_even_a_bleak_soul():
    # the ground is present in all -- a dark-tempered soul, not clinging, still warms
    a = _agent(temp=-0.6)
    dark = a.felt_mood()
    a.ground_enabled = True
    lifted = a.felt_mood()
    assert lifted > dark
