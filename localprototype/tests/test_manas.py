"""Stage-4 manas (appropriating grip) tests.

Pins: (1) the grip is a no-op when released (default), so nothing existing changes;
(2) when clamped it HOLDS self-relevant memories against decay and AMPLIFIES aversive
ones -- and does so via memory salience/emotion, not the reflect read; (3) self_relevance
ranks loss (mine) above mundane world-stuff. Substrate is deterministic; the self_relevance
sign test forces the Jaccard fallback so it runs without Ollama, using on-the-nose phrases."""

import pytest

from agent import manas
from agent.agent import Agent
from agent.memory import Memory
from services import embed
from services.llm import MockLLM


def _agent(grip: float):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.grip = grip
    return a


def test_grip_released_is_noop():
    a = _agent(0.0)
    a.memory.items = [Memory("my loss", 0.6, 0, 0, source="self", emotion=-0.5)]
    before = (a.memory.items[0].salience, a.memory.items[0].emotion)
    manas.apply(a, now=1)
    after = (a.memory.items[0].salience, a.memory.items[0].emotion)
    assert before == after


def test_grip_holds_salience_and_amplifies_aversive_self_memory():
    embed.use_jaccard_only(True)   # deterministic: relevance falls back to source
    try:
        a = _agent(1.0)
        m = Memory("my loss and my grief", 0.6, 0, 0, source="self", emotion=-0.5)
        a.memory.items = [m]
        manas.apply(a, now=1)
        assert m.salience > 0.6        # HOLD: resisted/raised against decay
        assert m.emotion < -0.5        # SECOND ARROW: aversive charge amplified
        assert m.emotion >= -1.0       # clamped
    finally:
        embed.use_jaccard_only(False)


def test_grip_leaves_neutral_self_memory_charge_alone():
    embed.use_jaccard_only(True)
    try:
        a = _agent(1.0)
        m = Memory("I keep the lamps", 0.6, 0, 0, source="self", emotion=0.0)
        a.memory.items = [m]
        manas.apply(a, now=1)
        assert m.emotion == 0.0        # no aversive charge to amplify
    finally:
        embed.use_jaccard_only(False)


def test_grip_via_step_when_enabled():
    a = _agent(1.0)
    a.memory.items = [Memory("my friend has died, my loss", 0.6, 0, 0,
                             source="self", emotion=-0.6)]
    a.step(now=1)                       # step() decays then applies the grip
    assert a.memory.items[0].emotion < -0.6   # net amplified despite decay


def test_grip_default_off_on_fresh_agent():
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    assert a.grip == 0.0


def test_self_relevance_ranks_mine_above_world():
    embed.use_jaccard_only(True)
    try:
        mine = manas.self_relevance("this is my loss, my friend, it is mine")
        world = manas.self_relevance("the market and the weather and the carts")
        assert mine > world
    finally:
        embed.use_jaccard_only(False)


# --- the WORLD's griefs, not just the soul's own words ------------------------------------
# Every test above uses source="self" -- the one source relevance_of() hardcodes to 1.0 when
# embeddings are down. But the losses the sim actually delivers (perceive() -> a death, a
# betrayal) are written source="event", and those are the charges the second arrow is FOR.
# These pin that path, so a regression there can't hide behind the source-only fallback.

def _grief_event(emotion: float = -0.9):
    """The canonical world-delivered loss, exactly as perceive() writes it."""
    return Memory("Your dearest friend Wren has died in the night.", 0.6, 0, 0,
                  source="event", emotion=emotion)


def test_grip_grips_a_world_delivered_grief_when_embeddings_are_up(monkeypatch):
    # WITH a semantic read available, an event-sourced loss must be judged self-relevant and
    # gripped like any other: held against decay, and its charge amplified (the second arrow).
    monkeypatch.setattr(manas, "relevance_of", lambda m: 0.0 if m.source == "doctrine" else 1.0)
    a = _agent(1.0)
    m = _grief_event()
    a.memory.items = [m]
    manas.apply(a, now=1)
    assert m.salience > 0.6        # HOLD: the grief looms larger, it is not let go of
    assert m.emotion < -0.9        # SECOND ARROW: "this happened to ME" magnified the wound


def test_transmutation_metabolizes_a_world_delivered_grief(monkeypatch):
    # the dharmic answer on the SAME memory: engaged (salience still held) AND unwounded
    # (charge digested toward clarity rather than amplified). See DHARMA.md.
    monkeypatch.setattr(manas, "relevance_of", lambda m: 0.0 if m.source == "doctrine" else 1.0)
    a = _agent(1.0)
    a.transmute = 0.85
    m = _grief_event()
    a.memory.items = [m]
    manas.apply(a, now=1)
    assert m.salience > 0.6        # ENGAGED: stays in full contact with the loss
    assert m.emotion > -0.9        # UNWOUNDED: the charge metabolized, not deepened


def test_source_only_fallback_cannot_grip_a_world_grief():
    # DOCUMENTS A KNOWN LIMITATION, so it is a decision and not a silent surprise.
    # With no embedding model, relevance_of() short-circuits to source membership and an
    # event-sourced loss scores 0.0 -- so the grip, the second arrow and transmutation are
    # ALL inert on exactly the memories the affect experiments are built around. Anything
    # reading manas offline (experiment_liberation / _transmutation / _prajna) is measuring
    # a disabled faculty. If this assertion ever starts FAILING, the fallback learned to see
    # world-delivered griefs -- delete this test and re-run those experiments.
    embed.use_jaccard_only(True)
    try:
        assert manas.relevance_of(_grief_event()) == 0.0
        a = _agent(1.0)
        m = _grief_event()
        a.memory.items = [m]
        manas.apply(a, now=1)
        assert (m.salience, m.emotion) == (0.6, -0.9)   # untouched: the dial did nothing
    finally:
        embed.use_jaccard_only(False)
