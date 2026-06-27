"""Stage-6 compassion tests (deterministic).

Pins: compassion is off by default; it DAMPS the threat->hostility reflex without
touching conviction (warm honesty, not capitulation); and it rewires the prompts
(warm system clause, warm-honest disagreement, the warm-turn override)."""

import pytest

from agent import compassion as C
from agent.agent import Agent
from services import embed
from services.llm import MockLLM, SpeechContext, build_system, build_user
from world.events import Utterance


@pytest.fixture(autouse=True)
def _jaccard():
    embed.use_jaccard_only(True)   # deterministic disagreement path, no Ollama
    yield
    embed.use_jaccard_only(False)


def _challenged(compassion: float):
    b = Agent("B", "Bram", (0, 0), "p", ["the old ways"], MockLLM(seed=1),
              seed=1, temperament=-0.4)
    b.belief = "hold to the old ways"
    b.compassion = compassion
    # opposed disposition (mood +) and addressed -> the dig-in / threat path fires
    b.hear(Utterance(speaker_id="A", text="break the old ways", tick=1,
                     addressed_to="B", source="ai", mood=+0.5), now=1, speaker_name="Ada")
    return b


def test_compassion_off_by_default():
    a = Agent("x", "X", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    assert a.compassion == 0.0


def test_compassion_damps_hostility():
    cold = _challenged(0.0).hostility.get("A", 0.0)
    warm = _challenged(0.8).hostility.get("A", 0.0)
    assert cold > 0.0
    assert warm < cold            # warmth softens the grievance...


def test_compassion_keeps_conviction():
    # ...but does NOT fold the view: conviction still hardens under challenge
    b = _challenged(0.8)
    assert b.conviction > 0.4     # default init is 0.4; a challenge raises it


def test_compassion_clause_in_system_prompt():
    warm = build_system(SpeechContext(name="B", persona="p", mood=0.0, compassion=0.8))
    cold = build_system(SpeechContext(name="B", persona="p", mood=0.0, compassion=0.0))
    assert "warmth and goodwill" in warm
    assert "warmth and goodwill" not in cold


def test_warm_disagreement_prompt():
    warm = build_user(SpeechContext(name="B", persona="p", mood=0.0,
                                    challenge="you are wrong", compassion=0.8))
    cold = build_user(SpeechContext(name="B", persona="p", mood=0.0,
                                    challenge="you are wrong", compassion=0.0))
    assert "acknowledge what is true" in warm          # warm-honest
    assert "Push back and" in cold                      # the old contempt-ish default


def test_warm_turn_overrides_to_connection():
    out = build_user(SpeechContext(name="B", persona="p", mood=0.0,
                                   warm_turn=True, reply_to_name="Ada",
                                   concept_mind=True))   # overrides even concept voice
    assert "simply connect" in out
    assert "Ada" in out
