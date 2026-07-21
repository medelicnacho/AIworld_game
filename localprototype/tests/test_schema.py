"""Tests for the attention schema (agent/schema.py, WORKSPACE_NEXT W1 / RESEARCH C1)."""

from agent.schema import AttentionSchema
from agent.workspace import Workspace
from world.sim import World


def _fed(seq):
    s = AttentionSchema()
    for i, x in enumerate(seq):
        s.observe(x, tick=i)
    return s


def test_off_by_default_everywhere():
    """THE RULE: a world that never asks gets no schema at all."""
    assert World().schema_enabled is False
    assert Workspace().schema is None


def test_accuracy_is_none_before_it_has_watched_anything():
    """No accuracy EXISTS yet -- reporting 0.0 would be a lie about a mind with no
    history (the summary() refusal discipline, scripts/stats.py)."""
    assert AttentionSchema().accuracy() is None


def test_it_learns_that_a_reign_persists():
    """The bug this was written after: the habit table recorded only CHANGES, so the
    model could never predict "stays put" -- which is right on ~77% of ticks when a
    reign lasts ~4. It scored 0.13 against a 0.40 base rate. A long reign must now be
    predicted to continue."""
    s = _fed(["Dread"] * 40)
    assert s.predict() == "Dread"
    assert s.accuracy() > 0.9


def test_it_learns_who_follows_whom():
    """A perfectly regular succession is learnable: after a run of Ache, Tending comes."""
    s = _fed((["Ache"] * 5 + ["Tending"] * 5) * 12)
    assert s.accuracy() > 0.7
    assert set(s.habit.get("Ache", {})) >= {"Ache", "Tending"}


def test_surprise_fires_only_on_a_real_change_and_then_fades():
    """A violation is the floor MOVING somewhere unexpected -- not a reign the guess
    merely under-called. And the felt surprise must decay, or it is a mood, not a spike."""
    s = _fed(["Dread"] * 30)
    assert s.surprise == 0.0                       # a settled, well-modelled stretch
    assert s.observe("Ember", tick=99) is True     # the floor jumped: surprised
    assert s.surprise > 0.5
    for t in range(20):                            # ... and it settles again
        s.observe("Ember", tick=100 + t)
    assert s.surprise < 0.2


def test_it_never_reads_the_mechanism_only_the_floor():
    """What makes it a SCHEMA and not a readout: it is fed the floor-holder alone --
    never the presence weights, never the fatigue. A mind watching itself from outside
    its own machinery."""
    s = _fed(["Dread", "Ache", "Dread"])
    assert set(vars(s)) == {"presence", "habit", "last", "guess", "surprise",
                            "seen", "hits", "violations"}


def test_describe_speaks_from_the_model_not_the_log():
    assert "not yet noticed" in AttentionSchema().describe()
    s = _fed(["Ache"] * 25)
    said = s.describe()
    assert "Ache" in said and said.endswith(".")


def test_wired_into_the_workspace_only_when_the_world_asks():
    from agent.agent import Agent
    from agent.psyche import FACULTY_OF, PSYCHE_CAST, endow_part
    from services.llm import MockLLM
    import random
    for asked in (False, True):
        w = World(rebirth_enabled=False, events_enabled=False)
        w.llm = MockLLM(seed=1)
        w.psyche = Workspace()
        w.schema_enabled = asked
        rng = random.Random(1)
        for i, (name, persona, temp, _aim, phr) in enumerate(PSYCHE_CAST):
            a = Agent(f"p{i}", name, (0, 0), persona, list(phr), w.llm,
                      seed=i, temperament=temp, lifespan=10 ** 9)
            endow_part(a, FACULTY_OF[name], rng)
            w.add(a)
        for t in range(30):
            w.step(speak=False)
        assert (w.psyche.schema is not None) is asked
