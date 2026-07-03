"""Tests for the E2 selection layer (world/sim.py + the stakes expression of the germ line).

No fitness is scored anywhere -- these pin that starvation and plenty are the WHOLE
pressure: metabolism makes living cost more, a starved lineage ENDS (no bardo -- the
one deliberate cosmology deviation, documented in _selection_tick), sustained surplus
earns a real birth (inherited germ line, provisioned by the parent, bonded from the
first breath), the space bound holds, the gates default OFF (existing worlds unchanged),
and old snapshots wake with the gates closed (THE RULE)."""

import random

from agent.agent import Agent
from agent.genesis import endow_faculties
from agent.genome import Genome, express, from_agent
from services.llm import MockLLM
from world.sim import World


def _world(selection=True, souls=2, lifespan=10 ** 6):
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    w.heredity_enabled = True
    w.selection_enabled = selection
    rng = random.Random(5)
    for i in range(souls):
        a = Agent(f"s{i}", f"F{i}", (i * 10.0, 0.0), "You are a working soul.",
                  [f"the well, day {i}"], w.llm, seed=i, temperament=0.0,
                  lifespan=lifespan)
        endow_faculties(a, rng)
        a.genome = from_agent(a, rng)
        w.add(a)
    return w


def test_metabolism_makes_living_cost_more():
    w = _world(selection=False)
    lean, hungry = w.agents
    express(Genome(grip=0.3, compassion=0.6, temperament=0.0, metabolism=0.1), lean)
    express(Genome(grip=0.3, compassion=0.6, temperament=0.0, metabolism=0.9), hungry)
    lean.stores = hungry.stores = 1.0
    w.commons = 0.0                        # nothing to fall back on: costs show plainly
    from world import stakes
    for t in range(10):
        # consume only (skip actions/hardship): pin the one claim under test
        for a in w.agents:
            need = stakes.CONSUME * (0.5 + a.metabolism)
            take = min(a.stores, need)
            a.stores -= take
    assert hungry.stores < lean.stores     # the same days cost the hungry germ line more


def test_a_starved_lineage_ends_without_a_bardo_return():
    # starvation must be REAL, not pinned: the stakes tick recomputes wellbeing from
    # stores + commons, so the honest way to starve a soul is to leave it NOTHING --
    # empty hands, empty commons -- while the other soul keeps its own larder
    w = _world(selection=True, souls=2)
    victim, other = w.agents
    ended = []
    w.bus.subscribe("starvation", ended.append)
    for t in range(400):
        victim.stores = 0.0                # nothing of its own...
        w.commons = 0.0                    # ...and no safety net: it goes unfed
        other.stores = 1.0                 # the other eats from its own larder
        with w.lock:
            w.step(speak=False)
        if victim not in w.agents:
            break
    assert victim not in w.agents          # the hazard opened past the grace, and took it
    assert ended == [victim.id]            # loud: an ended lineage is an event
    assert not w._bardo                    # NO return -- differential survival needs ends
    assert all(not a.id.startswith("stream:") for a in w.agents)


def test_sustained_surplus_earns_a_provisioned_bonded_birth():
    w = _world(selection=True, souls=1)
    parent = w.agents[0]
    for t in range(World.BREED_TICKS + 10):
        parent.wellbeing = 0.9             # thriving, sustained
        parent.stores = 1.2
        w.commons = 8.0
        with w.lock:
            w.step(speak=False)
        if len(w.agents) > 1:
            break
    child = next(a for a in w.agents if a.id.startswith("born:"))
    assert child.genome.lineage == parent.id            # the germ line descended...
    assert child.grip == child.genome.grip              # ...and was EXPRESSED
    assert child.stores > 0                             # provisioned by the parent
    assert child.bonds[parent.id].trust > 0             # bonded from the first breath
    assert parent.bonds[child.id].trust > 0
    assert child.lifespan == parent.lifespan            # the lineage's scale


def test_the_world_is_a_space_not_a_score():
    w = _world(selection=True, souls=1)
    w.max_souls = 3
    w.hardship_interval = 10 ** 9          # no weather: this test pins the CAP alone
                                           # (with weather on, hardships break the
                                           # thriving streak -- the ecology working)
    parent = w.agents[0]
    for t in range(World.BREED_TICKS * 6):
        for a in w.agents:
            a.wellbeing, a.stores = 0.9, 1.2
        w.commons = 8.0
        with w.lock:
            w.step(speak=False)
    assert len(w.agents) == 3              # full is full; nobody outbreeds the land


def test_gates_off_means_the_old_world_exactly():
    w = _world(selection=False, souls=1)
    soul = w.agents[0]
    for t in range(120):
        soul.wellbeing = 0.0               # starving forever...
        with w.lock:
            w.step(speak=False)
    assert soul in w.agents                # ...and nothing happens: the gate is real


def test_old_snapshots_wake_with_the_gates_closed():
    w = _world(selection=True)
    state = w.__getstate__()
    for k in ("selection_enabled", "max_souls", "_born_live"):
        del state[k]
    w2 = object.__new__(World)
    w2.__setstate__(state)
    assert w2.selection_enabled is False
    assert w2.max_souls == 20 and w2._born_live == 0
