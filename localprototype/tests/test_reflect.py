"""Stage-1 reflect() + affective-substrate tests (deterministic, MockLLM).

Two things are pinned here: (1) reflect() wiring -- it reads memory, writes a
'reflection' back, and is a no-op when there's nothing of one's own to reflect on;
(2) the affective SUBSTRATE -- a single self, run through the scripted grief
protocol, shows grief / habituation / recurrence in its lived mood. The real
equanimity signal needs a model (experiment_affect.py --llm ollama); here the
canned Mock reflection is net-positive, so we only assert the wiring moves mood
the intended direction."""

import pytest

from agent.agent import Agent
from agent.reflect import reflect
from services.llm import MockLLM
from services import embed

import experiment_affect as exp


@pytest.fixture(autouse=True)
def _jaccard():
    # hermetic: reflect()'s equanimity emotion path uses embeddings when up; force
    # the Jaccard fallback so these run deterministically without Ollama (then
    # reflect writes emotion=0 and memory.write derives the canned line's valence).
    embed.use_jaccard_only(True)
    yield
    embed.use_jaccard_only(False)


def _agent():
    llm = MockLLM(seed=1)
    a = Agent("self", "Aldous", (0.0, 0.0), "a quiet life", ["a quiet life"],
              llm, seed=1, temperament=0.0)
    return a, llm


def test_reflect_writes_reflection_memory():
    a, llm = _agent()
    a.memory.write("Wren has died", tick=1, source="event", emotion=-0.9)
    text = reflect(a, llm, now=2)
    assert text
    assert any(m.source == "reflection" for m in a.memory.items)


def test_reflect_noop_when_only_doctrine():
    # a fresh agent carries only doctrine memories; reflect() filters those out,
    # so with nothing of its OWN lived experience present it does nothing.
    llm = MockLLM(seed=1)
    a = Agent("self", "Aldous", (0.0, 0.0), "p", [], llm, seed=1)
    assert reflect(a, llm, now=1) is None


def test_reflect_enabled_defaults_off():
    a, _ = _agent()
    assert a.reflect_enabled is False


def test_substrate_grief_habituation_recurrence():
    """A single self has legible feelings: the prerequisite the crowded --world
    transcript lacks. Deterministic from events + decay, no LLM cleverness."""
    base = exp.run_arm(MockLLM(seed=11), 11, do_reflect=False)
    s = exp._signatures(base["mood"])
    assert s["grief"] > 0.05, s
    assert s["habituation"] > 0.02, s
    assert s["recurrence"] > 0.02, s


def test_reflect_moves_mood_vs_baseline():
    """Plumbing: an equanimous reflection written back lifts the lived mood through
    grief vs an identical no-reflect run (the real content test needs a model)."""
    base = exp.run_arm(MockLLM(seed=11), 11, do_reflect=False)
    refl = exp.run_arm(MockLLM(seed=11), 11, do_reflect=True)
    sb = exp._signatures(base["mood"])
    sr = exp._signatures(refl["mood"])
    assert len(refl["reflections"]) > 0
    assert sr["mean_post"] > sb["mean_post"] + 0.02


def test_interoception_flag_feeds_the_body_as_sensation_never_numbers():
    """OFF by default (her live self untouched); ON + a high grip puts a felt-sense
    line in the prompt -- 'tightness', never 'grip'/'holding'/numbers (the experiment
    must not put its answer in her mouth); a calm body says nothing."""
    from agent import reflect as _reflect
    from agent.agent import Agent
    from services.llm import MockLLM

    a = Agent("s0", "Cael", (0.0, 0.0), "You are Cael.", ["the well"],
              MockLLM(seed=7), seed=3, temperament=0.0, lifespan=10 ** 6)
    a.memory.write("a long day at the well", tick=1, source="event")
    a.grip = 0.95
    prompt, _sys = _reflect.prepare(a)
    assert "Your body" not in prompt                     # off by default
    a.interoception_enabled = True
    prompt, _sys = _reflect.prepare(a)
    assert "tightness in you" in prompt
    body_line = prompt.split("Your body")[1]
    assert "grip" not in body_line.lower() and "holding" not in body_line.lower()
    assert not any(c.isdigit() for c in body_line)
    a.grip = 0.0
    prompt, _sys = _reflect.prepare(a)
    assert "Your body" not in prompt                     # a calm body says nothing
