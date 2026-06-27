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
