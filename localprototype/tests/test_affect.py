"""Semantic equanimity measure -- the #1 fix for affect measurement validity.

Deterministic: forces the Jaccard fallback so it runs without Ollama. On-the-nose
phrases (sharing words with the anchors) exercise the sign; the real cosine signal
that separates sad-toned ACCEPTANCE from sad-toned RUMINATION needs embeddings and
is shown live by experiment_affect.py / probe runs."""

import pytest

from agent import affect
from services import embed


@pytest.fixture(autouse=True)
def _jaccard():
    embed.use_jaccard_only(True)
    yield
    embed.use_jaccard_only(False)


def test_empty_is_zero():
    assert affect.equanimity("") == 0.0
    assert affect.equanimity_emotion("") == 0.0


def test_acceptance_scores_positive():
    eq = affect.equanimity(
        "I hold this lightly without grasping, and I accept it as it is, and let it pass.")
    assert eq > 0.0, eq


def test_rumination_scores_negative():
    eq = affect.equanimity(
        "I cannot stop thinking about this; I am trapped and I cannot let it go.")
    assert eq < 0.0, eq


def test_acceptance_ranks_above_rumination():
    acc = affect.equanimity("I accept it as it is and let it pass through me.")
    rum = affect.equanimity("I cannot let it go and I am trapped in it.")
    assert acc > rum


def test_emotion_is_clamped():
    for s in ["I accept it as it is and let it pass and hold it lightly with calm.",
              "I cannot stop and I am trapped and I cannot let it go, drowning."]:
        assert -affect.EMOTION_CAP <= affect.equanimity_emotion(s) <= affect.EMOTION_CAP
