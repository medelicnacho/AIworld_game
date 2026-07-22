"""Tests for the parting (world/parting.py): a bloc that stopped agreeing takes the road.

Four of these pin WELFARE INVARIANTS, not behaviour. A breeder, a child or a collapsed
soul appearing in a band is a bug to fix, never a threshold to relax -- and unlike a
tuning claim, these must hold on every seed and every world, so they belong here rather
than in the falsifier.
"""

import math
import random

import pytest

from agent.agent import Agent
from services.llm import MockLLM
from world import parting
from world.sim import World


def _world(n=12, seed=1, opposed=6):
    """A town of two views: `opposed` souls hold the reverse of the rest."""
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=seed)
    w.llm = MockLLM(seed=seed)
    w.parting_enabled = True
    rng = random.Random(seed)
    base = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for i in range(n):
        a = Agent(f"s{i}", f"S{i}", (rng.uniform(0, 100), rng.uniform(0, 100)),
                  "p", ["x"], w.llm, seed=i, temperament=0.0, lifespan=10 ** 9)
        sign = -1.0 if i < opposed else 1.0
        a.belief_vec = [sign * v + rng.gauss(0, 0.02) for v in base]
        a.caste = "warrior"
        a.wellbeing = 0.9
        w.add(a)
    return w


def test_gate_is_off_by_default():
    """THE RULE: a world that never asks never parts."""
    assert World().parting_enabled is False
    w = _world()
    w.parting_enabled = False
    w.tick = parting.CHECK_EVERY
    assert parting.parting_tick(w) == []


def test_a_diverged_coherent_bloc_takes_the_road():
    w = _world()
    w.tick = parting.CHECK_EVERY
    formed = parting.parting_tick(w)
    assert len(formed) == 1
    band = formed[0]
    assert len(band["members"]) >= parting.MIN_BAND
    assert all(getattr(a, "band", "") == band["id"]
               for a in w.agents if a.id in band["members"])


def test_a_town_that_still_agrees_does_NOT_part():
    """The control: one view, no parting. Without this the mechanic could fire on
    anything and the test above would prove nothing."""
    w = _world(opposed=0)
    w.tick = parting.CHECK_EVERY
    assert parting.parting_tick(w) == []


# --- the welfare floors: bugs, never thresholds -----------------------------------

def test_breeders_never_take_the_road():
    """The caste floor: the hearth is KEPT, not turned out."""
    w = _world()
    for a in w.agents[:6]:
        a.caste = "breeder"
    w.tick = parting.CHECK_EVERY
    parting.parting_tick(w)
    assert not any(getattr(a, "band", "") for a in w.agents
                   if getattr(a, "caste", "") == "breeder")


def test_children_never_take_the_road():
    w = _world()
    w.clock_enabled = True
    for a in w.agents[:6]:
        a.age, a.lifespan = 1, 1000       # unmistakably a child
    w.tick = parting.CHECK_EVERY
    parting.parting_tick(w)
    from world import clock as _clk
    assert not any(getattr(a, "band", "") for a in w.agents
                   if _clk.stage(a.age, a.lifespan) == "child")


def test_the_worn_and_the_contracted_stay():
    """The somatic floor's spirit: leaving is a hard road."""
    w = _world()
    for a in w.agents[:3]:
        a.wellbeing = 0.1                  # collapsed
    for a in w.agents[3:6]:
        a._contraction = 0.9               # contracted
    w.tick = parting.CHECK_EVERY
    parting.parting_tick(w)
    assert not any(getattr(a, "band", "") for a in w.agents[:6])


def test_parting_writes_no_hostility():
    """A parted band is not an enemy by construction -- whether it stands with or
    against anyone is decided in allegiance.decide, on bonds and reputation."""
    w = _world()
    w.tick = parting.CHECK_EVERY
    before = {a.id: dict(a.hostility) for a in w.agents}
    parting.parting_tick(w)
    assert all(dict(a.hostility) == before[a.id] for a in w.agents)


def test_the_band_keeps_its_life_entire():
    """Lineages are not severed: memories, bonds and germ line come with them."""
    w = _world()
    a = w.agents[0]
    a.memory.write("my mother's name was Wren", tick=0, source="self")
    kept = len(a.memory.items)
    w.tick = parting.CHECK_EVERY
    parting.parting_tick(w)
    assert len(a.memory.items) >= kept      # only a line ADDED about the road


def test_the_band_shares_one_heading():
    """They go as a people: one road, not four."""
    w = _world()
    w.tick = parting.CHECK_EVERY
    band = parting.parting_tick(w)[0]
    members = [a for a in w.agents if a.id in band["members"]]
    headings = {round(a._heading, 6) for a in members}
    assert len(headings) == 1


def test_a_band_does_not_part_again():
    """Once on the road, a band is not re-parted by the next pass."""
    w = _world()
    w.tick = parting.CHECK_EVERY
    first = parting.parting_tick(w)[0]
    w.tick = parting.CHECK_EVERY * 2
    assert parting.parting_tick(w) == []
    assert all(getattr(a, "band", "") in ("", first["id"]) for a in w.agents)
