"""Stage bodhicitta tests (deterministic).

Pins: off by default; a moved soul PROACTIVELY turns to the most-suffering soul it knows
of (even unprompted); the prompts carry the aim + the comfort turn."""

import pytest

from agent import compassion as C
from agent.agent import Agent
from services.llm import MockLLM, SpeechContext, build_system, build_user


@pytest.fixture
def _always_turn():
    old = C.BODHICITTA_CHANCE
    C.BODHICITTA_CHANCE = 1.0
    yield
    C.BODHICITTA_CHANCE = old


def _soul(bod):
    a = Agent("B", "Bram", (0, 0), "p", ["the morning bread"], MockLLM(seed=1),
              seed=1, temperament=0.2)
    a.bodhicitta = bod
    return a


def test_bodhicitta_off_by_default():
    assert _soul(0.0).bodhicitta == 0.0


def test_proactively_turns_to_the_suffering(_always_turn):
    b = _soul(0.8)
    b._others_mood = {"S": -0.5, "Q": 0.3}     # S is suffering, Q is fine
    b._others_name = {"S": "Silas", "Q": "Quill"}
    ctx, addressed, _ = b.prepare_speech(recent=[])
    assert ctx.bodhicitta_turn is True
    assert addressed == "S"                     # turned toward the suffering one, not Q
    assert ctx.reply_to_name == "Silas"


def test_no_turn_when_no_one_suffers(_always_turn):
    b = _soul(0.8)
    b._others_mood = {"Q": 0.3}                 # nobody below the suffering threshold
    b._others_name = {"Q": "Quill"}
    ctx, _addr, _ = b.prepare_speech(recent=[])
    assert ctx.bodhicitta_turn is False


def test_off_soul_does_not_seek(_always_turn):
    b = _soul(0.0)                              # bodhicitta off
    b._others_mood = {"S": -0.5}
    b._others_name = {"S": "Silas"}
    ctx, _addr, _ = b.prepare_speech(recent=[])
    assert ctx.bodhicitta_turn is False


def test_prompts_carry_aim_and_comfort():
    sysp = build_system(SpeechContext(name="B", persona="p", mood=0.0, bodhicitta=0.8))
    assert "bodhicitta" in sysp.lower()
    out = build_user(SpeechContext(name="B", persona="p", mood=0.0,
                                   bodhicitta_turn=True, reply_to_name="Silas",
                                   concept_mind=True))   # overrides voice mode
    assert "Silas" in out and "comfort" in out.lower()
