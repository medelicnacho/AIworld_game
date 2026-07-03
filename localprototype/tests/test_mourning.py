"""Tests for grief-for-the-fallen (World._mourn, both death channels).

Pinned: a bonded survivor writes a charged grief memory when its friend dies (deeper love,
deeper grief), tagged as a story seed so the dead can become legend; an ENEMY notes the
death colder and quieter; a stranger feels nothing (a stranger's death is weather); the
loss is APPRAISED against the survivor's days (§5.15 riding along); starvation deaths
(E2's new channel) are mourned exactly like the wheel's; and the gate defaults OFF so
every recorded verdict predating grief is untouched."""

import random

from agent.agent import Agent
from agent.bond import Bond
from agent.genesis import endow_faculties
from services.llm import MockLLM
from world.sim import World


def _town(mourning=True, lifespans=(3, 10 ** 6, 10 ** 6, 10 ** 6)):
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.mourning_enabled = mourning
    w.bardo_ticks = (50, 60)             # keep the bardo out of the way of these tests
    rng = random.Random(5)
    names = ("Doomed", "Friend", "Enemy", "Stranger")
    for i, (name, span) in enumerate(zip(names, lifespans)):
        a = Agent(f"s{i}", name, (i * 10.0, 0.0), f"You are {name}.", ["the well"],
                  w.llm, seed=i, temperament=0.0, lifespan=span)
        endow_faculties(a, rng)
        a.bond_enabled = True
        w.add(a)
    doomed, friend, enemy, stranger = w.agents
    friend.bonds[doomed.id] = Bond(trust=0.8, history=2.0)     # deep love
    enemy.bonds[doomed.id] = Bond(trust=-0.6, history=1.0)     # old quarrel
    return w


def _grief(agent):
    return [m for m in agent.memory.items if m.lore_id.startswith("death:")]


def test_the_loss_lands_by_bond_and_becomes_a_story_seed():
    w = _town()
    doomed, friend, enemy, stranger = w.agents
    for _ in range(6):
        with w.lock:
            w.step(speak=False)
    assert doomed not in w.agents                       # the wheel took it
    (g,) = _grief(friend)
    # the raw charge (-0.72 for trust 0.8) arrives APPRAISED (§5.15): a neutral-days
    # survivor half-braces, so the landed grief is softer than the raw -- the ordering,
    # not the absolute, is the claim (and appraisal softening is the feature working)
    assert "loved them" in g.text and g.emotion < -0.25
    assert g.lore_id.startswith("death:s0:")            # the dead can become legend
    (e,) = _grief(enemy)
    assert "quarrel" in e.text and e.emotion < 0        # colder...
    assert e.emotion > g.emotion                        # ...and quieter than grief
    assert _grief(stranger) == []                       # a stranger's death is weather


def test_deeper_love_grieves_deeper():
    w = _town()
    doomed, friend, enemy, stranger = w.agents
    stranger.bonds[doomed.id] = Bond(trust=0.3, history=0.2)   # a mild acquaintance
    for _ in range(6):
        with w.lock:
            w.step(speak=False)
    deep, mild = _grief(friend)[0], _grief(stranger)[0]
    assert deep.emotion < mild.emotion                  # more love, more grief


def test_starvation_deaths_are_mourned_too():
    w = _town(lifespans=(10 ** 6, 10 ** 6, 10 ** 6, 10 ** 6))
    w.stakes_enabled = True
    w.selection_enabled = True
    w.heredity_enabled = True
    doomed, friend, enemy, stranger = w.agents
    for _ in range(400):
        doomed.stores = 0.0                             # nothing of its own...
        w.commons = 0.0                                 # ...and no safety net
        friend.stores = enemy.stores = stranger.stores = 1.0
        with w.lock:
            w.step(speak=False)
        if doomed not in w.agents:
            break
    assert doomed not in w.agents                       # hunger took it (E2's channel)
    assert _grief(friend)                               # and hunger has faces
    assert _grief(stranger) == []


def test_the_gate_defaults_off_and_holds():
    w = _town(mourning=False)
    for _ in range(6):
        with w.lock:
            w.step(speak=False)
    assert all(_grief(a) == [] for a in w.agents)       # recorded verdicts predate grief

    assert World().mourning_enabled is False            # the default is the default
    state = _town().__getstate__()
    del state["mourning_enabled"]                       # a pre-grief snapshot
    w2 = object.__new__(World)
    w2.__setstate__(state)
    assert w2.mourning_enabled is False                 # THE RULE
