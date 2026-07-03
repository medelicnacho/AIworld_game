"""Tests for witnessed karma (agent/witness.py + the stakes hooks).

Pinned: a visible deed moves every PRESENT soul's expectation of the actor (less than a
suffered one would -- hearing of a knife is not feeling it); some witnesses TELL it, with
the charge in the WORDS (the pledge lesson) and the conduct tag that lets it gossip;
distance bounds who counts as present for embodied actors while a placeless actor (the
player) is seen by all; and the stakes layer's shares and scarcity-hoards call it."""

import random

from agent import witness
from agent.agent import Agent
from agent.genesis import endow_faculties
from agent.memory import valence
from services.llm import MockLLM
from world.sim import World


def _town(n=4, spread=10.0):
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    rng = random.Random(5)
    for i in range(n):
        a = Agent(f"s{i}", f"F{i}", (i * spread, 0.0), "You are a working soul.",
                  ["the well"], w.llm, seed=i, temperament=0.0, lifespan=10 ** 6)
        endow_faculties(a, rng)
        a.bond_enabled = True
        w.add(a)
    return w


def test_a_visible_deed_moves_everyone_present():
    w = _town()
    seen = witness.witnessed(w, "player", "the far-walker", "kindness", now=5)
    assert seen == 4                                  # placeless actor: seen by all
    assert all(a._conduct_expect["player"] > 0 for a in w.agents)
    witness.witnessed(w, "stranger", "a stranger", "meanness", now=6)
    assert all(a._conduct_expect["stranger"] < 0 for a in w.agents)


def test_hearing_of_a_knife_is_not_feeling_it():
    from agent.expectation import BOND_EXPECT_RATE
    assert witness.THIRD_RATE < BOND_EXPECT_RATE      # witnessed < suffered, by design


def test_the_telling_carries_its_charge_in_its_words():
    w = _town()
    w._rng = random.Random(1)                          # some witnesses will tell
    witness.witnessed(w, "player", "the far-walker", "meanness", now=5)
    told = [m for a in w.agents for m in a.memory.items
            if m.lore_id == "conduct:player"]
    assert told                                        # somebody will gossip this
    assert all(valence(m.text) < 0 for m in told)      # and the WORDS carry the charge


def test_distance_bounds_embodied_witnesses():
    w = _town(n=3, spread=120.0)                       # one neighbour in reach, one beyond
    actor = w.agents[0]
    seen = witness.witnessed(w, actor.id, actor.name, "kindness", now=5)
    assert seen == 1                                   # only the neighbour within radius
    assert "s0" not in w.agents[2]._conduct_expect     # the far soul saw nothing


def test_the_stakes_layer_calls_it():
    from world import stakes
    w = _town()
    w.stakes_enabled = True
    sharer, needy, watcher, far = w.agents
    needy.wellbeing = 0.1
    w.commons = 2.0
    stakes.apply_action(sharer, "share", w, now=9)
    assert watcher._conduct_expect.get(sharer.id, 0) > 0   # the share was SEEN
    hoarder = watcher
    stakes.apply_action(hoarder, "hoard", w, now=10)       # while needy still starves
    assert sharer._conduct_expect.get(hoarder.id, 0) < 0   # ...and so was the raid
