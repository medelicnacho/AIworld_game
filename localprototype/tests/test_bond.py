"""Stage-2 dyadic bond tests (pure substrate, deterministic, no model).

Pins the three properties that make a bond a relationship rather than a scalar:
asymmetry, inertia (loyalty resists evidence), and memory (betrayal is remembered
and finite loyalty eventually breaks)."""

from agent.agent import Agent
from agent.bond import Bond, describe
from services.llm import MockLLM


def test_warm_raises_trust_and_history():
    b = Bond()
    b.warm()
    assert b.trust > 0.0
    assert b.history > 0.0


def test_betray_drops_trust_and_records_wound():
    b = Bond()
    for _ in range(5):
        b.warm()
    t0, h0 = b.trust, b.history
    b.betray(0.6)
    assert b.trust < t0
    assert b.wounds == 1
    assert b.history < h0          # the buffer itself is eroded (memory)


def test_inertia_loyal_survives_shallow_shatters():
    loyal = Bond()
    for _ in range(12):
        loyal.warm()
    shallow = Bond()
    shallow.warm()
    loyal.betray(0.6)
    shallow.betray(0.6)
    assert loyal.trust > 0.0       # loyalty resists one betrayal
    assert shallow.trust < 0.0     # a shallow bond breaks
    assert loyal.trust > shallow.trust


def test_asymmetry_is_directional():
    a, b = Bond(), Bond()
    for _ in range(10):
        a.warm()                   # only A invests
    assert a.trust - b.trust > 0.5


def test_memory_repeated_betrayal_breaks_loyal_bond():
    deep = Bond()
    for _ in range(12):
        deep.warm()
    broke = None
    for i in range(1, 7):
        deep.betray(0.6)
        if broke is None and deep.trust < 0:
            broke = i
    assert broke is not None and broke > 1   # buffered at first, breaks later
    assert deep.wounds == 6


def test_describe_reflects_state():
    warm = Bond()
    for _ in range(12):
        warm.warm()
    assert "love" in describe(warm, "Bram").lower() or "warm" in describe(warm, "Bram").lower()
    wounded = Bond()
    wounded.betray(0.9)
    assert "wounded" in describe(wounded, "Bram").lower()


def test_agent_has_opt_in_bonds():
    a = Agent("x", "X", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    assert a.bond_enabled is False
    assert a.bonds == {}


def test_feel_warms_then_cools_without_wound():
    b = Bond()
    b.feel(0.3)
    assert b.trust > 0.0 and b.history > 0.0
    t = b.trust
    b.feel(-0.3)
    assert b.trust < t
    assert b.wounds == 0          # ambient coolness is not a remembered betrayal


def test_hear_forms_bond_when_enabled():
    from services import embed
    from world.events import Utterance
    embed.use_jaccard_only(True)   # deterministic: uses the disposition fallback
    try:
        a = Agent("a", "A", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1, temperament=0.5)
        a.bond_enabled = True
        a.hear(Utterance(speaker_id="b", text="we stand together", tick=1,
                         source="ai", mood=0.6), now=1, speaker_name="B")
        assert "b" in a.bonds and a.bonds["b"].trust > 0.0
    finally:
        embed.use_jaccard_only(False)


def test_hear_no_bond_when_disabled():
    from world.events import Utterance
    a = Agent("a", "A", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1, temperament=0.5)
    a.hear(Utterance(speaker_id="b", text="hi", tick=1, source="ai", mood=0.6),
           now=1, speaker_name="B")
    assert a.bonds == {}           # opt-in: off by default, graph untouched
