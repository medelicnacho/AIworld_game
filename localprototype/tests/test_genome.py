"""Tests for the E1 germ line (agent/genome.py + the wheel's heredity gate).

Pinned: reflection keeps mutation inside the bounds without piling on the walls (the
clamping bias the drift null would rightly flag); one crossing perturbs by about sigma
and stamps the lineage; express writes the flesh; the wheel carries the genome ONLY when
heredity is on (the default wheel still re-rolls -- the gate is real); a founder without
an explicit genome gets one captured at death; old snapshots wake with the gate closed
(THE RULE); and a town with genomes survives the JSON snapshot round-trip."""

import random

from agent.genome import BOUNDS, DIALS, Genome, _reflect, express, from_agent, inherit


def test_reflection_stays_in_bounds_without_wall_pileup():
    rng = random.Random(3)
    lo, hi = 0.0, 1.0
    walked = 0.02                                  # start near the wall
    at_wall = 0
    for _ in range(4000):
        walked = _reflect(walked + rng.gauss(0.0, 0.05), lo, hi)
        assert lo <= walked <= hi
        at_wall += walked in (lo, hi)
    assert at_wall < 5                             # reflection, not clamp-and-stick
    assert _reflect(-0.07, 0.0, 1.0) == 0.07       # folded back, energy kept
    assert _reflect(1.03, 0.0, 1.0) == 0.97
    assert abs(_reflect(-1.2, -1.0, 1.0) - (-0.8)) < 1e-12   # temperament's range too


def test_one_crossing_perturbs_by_about_sigma_and_stamps_lineage():
    rng = random.Random(11)
    parent = Genome(grip=0.4, compassion=0.6, temperament=0.1)
    kids = [inherit(parent, rng, "s3") for _ in range(300)]
    assert all(k.lineage == "s3" for k in kids)
    assert parent.lineage == ""                    # the parent is untouched
    for dial in DIALS:
        diffs = [abs(getattr(k, dial) - getattr(parent, dial)) for k in kids]
        assert 0.01 < sum(diffs) / len(diffs) < 0.06    # ~sigma, not a re-roll
        lo, hi = BOUNDS[dial]
        assert all(lo <= getattr(k, dial) <= hi for k in kids)


def test_express_writes_the_flesh():
    class _A:
        pass
    a = _A()
    g = Genome(grip=0.33, compassion=0.77, temperament=-0.2,
               metabolism=0.61, boldness=0.15)
    express(g, a)
    assert (a.grip, a.compassion, a.temperament) == (0.33, 0.77, -0.2)
    assert (a.metabolism, a.boldness) == (0.61, 0.15)   # dormant until E2, but carried


def _wheel_world(heredity: bool):
    from agent.agent import Agent
    from agent.genesis import endow_faculties
    from services.llm import MockLLM
    from world.sim import World
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.heredity_enabled = heredity
    w.bardo_ticks = (1, 2)
    rng = random.Random(5)
    a = Agent("s0", "Vesper", (0.0, 0.0), "You are Vesper.", ["the ale"],
              w.llm, seed=1, temperament=0.2, lifespan=3)
    endow_faculties(a, rng)
    a.genome = from_agent(a, rng)
    w.add(a)
    return w, a


def test_the_wheel_carries_the_germ_line_when_and_only_when_on():
    for heredity in (True, False):
        w, founder = _wheel_world(heredity)
        pg = founder.genome
        for t in range(14):
            with w.lock:
                w.step(speak=False)
            newborn = next((x for x in w.agents if x.id.startswith("stream:")), None)
            if newborn is not None:
                break
        assert newborn is not None, "the wheel should have turned by now"
        child = getattr(newborn, "genome", None)
        if heredity:
            assert child is not None and child.lineage == "s0"
            for dial in DIALS:                     # one crossing: near the parent
                assert abs(getattr(child, dial) - getattr(pg, dial)) < 0.15
            assert newborn.grip == child.grip      # ...and EXPRESSED, not just carried
            assert newborn.compassion == child.compassion
        else:
            assert child is None                   # the default wheel still re-rolls


def test_founder_without_explicit_genome_is_captured_at_death():
    w, founder = _wheel_world(True)
    del founder.__dict__["genome"]                 # a soul from before the germ line
    for t in range(14):
        with w.lock:
            w.step(speak=False)
        newborn = next((x for x in w.agents if x.id.startswith("stream:")), None)
        if newborn is not None:
            break
    assert newborn is not None and newborn.genome.lineage == "s0"


def test_old_snapshots_wake_with_the_gate_closed():
    w, _ = _wheel_world(True)
    state = w.__getstate__()
    del state["heredity_enabled"], state["heredity_sigma"]  # a pre-E1 snapshot
    from world.sim import World
    w2 = object.__new__(World)
    w2.__setstate__(state)
    assert w2.heredity_enabled is False            # THE RULE: defaults, never a freeze
    assert w2.heredity_sigma == 0.03


def test_genomes_survive_the_json_town_snapshot():
    from services.llm import MockLLM
    from world.serialize import world_from_json, world_to_json
    w, founder = _wheel_world(True)
    j = world_to_json(w)
    w2 = world_from_json(j, MockLLM(seed=7))
    g = w2.agents[0].genome
    assert g.lineage == founder.genome.lineage
    assert g.grip == founder.genome.grip           # the germ line rides the ~o tag
