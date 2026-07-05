"""Tests for the land (world/regions.py + the stakes routing).

Pinned: geometry maps positions to regions; labour lands where the labourer STANDS,
scaled by that ground's soil; hunger draws from the pool underfoot; a soul on a harsh
ridge beside a fat vale genuinely starves harder (the measured graded-scarcity
requirement, now geometry); and every world that never enables regions keeps the old
single-commons behaviour exactly (THE RULE)."""

import random

from agent.agent import Agent
from services.llm import MockLLM
from world import regions as R
from world import stakes
from world.sim import World


def _soul(w, sid, pos):
    a = Agent(sid, sid, pos, f"You are {sid}.", ["the well"], MockLLM(seed=1),
              seed=int(sid[-1]), temperament=0.0, lifespan=10 ** 6)
    w.add(a)
    return a


def _world(regions_on=True, seed=3):
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    if regions_on:
        w.regions_enabled = True
        w.regions = R.Regions(bounds=(900.0, 600.0), seed=seed)
    return w


def test_geometry_and_names():
    r = R.Regions(seed=1)
    assert r.index((0, 0)) == 0 and r.index((899, 599)) == R.COLS * R.ROWS - 1
    assert len(set(r.names)) == R.COLS * R.ROWS
    rich = max(range(6), key=lambda i: r.yields[i])
    assert r.names[rich] == "the vale"              # the fattest land is always the vale


def test_labour_lands_underfoot_scaled_by_soil():
    w = _world()
    rich = max(range(6), key=lambda i: w.regions.yields[i])
    poor = min(range(6), key=lambda i: w.regions.yields[i])
    cx = lambda i: ((i % R.COLS) * 300 + 150, (i // R.COLS) * 300 + 150)
    a = _soul(w, "s1", cx(rich))
    b = _soul(w, "s2", cx(poor))
    before_r, before_p = w.regions.pools[rich], w.regions.pools[poor]
    stakes.apply_action(a, "work", w, now=1)
    stakes.apply_action(b, "work", w, now=1)
    gain_r = w.regions.pools[rich] - before_r
    gain_p = w.regions.pools[poor] - before_p
    assert gain_r > gain_p > 0                       # same sweat, different soil
    assert abs(gain_r / gain_p - w.regions.yields[rich] / w.regions.yields[poor]) < 1e-6


def test_hunger_draws_from_the_pool_underfoot():
    w = _world()
    w.commons_first = True
    i = w.regions.index((150, 150))
    a = _soul(w, "s1", (150.0, 150.0))
    a.stores = 0.0
    w.regions.pools = [0.0] * 6
    w.regions.pools[i] = 1.0
    stakes.step(w)
    # (step also runs the soul's ACTION -- a work can outweigh a meal in the pool --
    # so locality is asserted through _met: fed at home, starving on empty ground)
    assert a._met > 0.9                              # ate from home ground
    # ...and a soul standing on an EMPTY region starves even if the vale is full
    j = (i + 3) % 6
    b = _soul(w, "s2", ((j % R.COLS) * 300 + 150.0, (j // R.COLS) * 300 + 150.0))
    b.stores = 0.0
    w.regions.pools = [0.0] * 6
    w.regions.pools[i] = 5.0                         # the vale groans with food...
    stakes.step(w)
    assert b._met < 0.2                              # ...and the crag still starves


def test_worlds_without_regions_are_untouched():
    w = _world(regions_on=False)
    a = _soul(w, "s1", (10.0, 10.0))
    before = w.commons
    stakes.apply_action(a, "work", w, now=1)
    assert w.commons > before                        # the single float, as ever
