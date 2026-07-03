"""Tests for the living time (world/clock.py + its gates in sim/stakes/her digest).

Pinned: the phase math cycles honestly; night pauses labour but never bellies or weather;
the seasons multiply what work returns (harvest plenty, winter want); each turn of season
is FELT once (an ambient, lore-tagged memory in every soul); children play, eat little,
and the starvation hazard never opens on them; elders tire at labour and their
story-memories resist decay (the legend-keepers); her digest reads the hour; and the
gate defaults OFF with snapshot defaults (THE RULE) -- every recorded verdict predates time."""

import random

from agent.agent import Agent
from agent.genesis import endow_faculties
from services.llm import MockLLM
from world import clock, stakes
from world.sim import World


def test_the_phase_math_cycles():
    assert clock.hour(0) == 0.0
    assert not clock.is_night(0)
    assert clock.is_night(75)                     # the last third of a 100-tick day
    assert clock.day_of(250) == 2
    assert clock.season(0) == "spring"
    assert clock.season(8 * 100) == "summer"      # 8 days on
    assert clock.season(31 * 100) == "winter"
    assert clock.season(32 * 100) == "spring"     # the year comes round
    assert clock.stage(10, 100) == "child"
    assert clock.stage(50, 100) == "adult"
    assert clock.stage(80, 100) == "elder"
    assert "deep night" in clock.time_clause(75)
    assert "harvest" in clock.time_clause(17 * 100)


def _soul(w, sid, name, lifespan=1000, age=300):
    a = Agent(sid, name, (0.0, 0.0), f"You are {name}.", ["the well"], w.llm,
              seed=int(sid[1]), temperament=0.0, lifespan=lifespan)
    endow_faculties(a, random.Random(3))
    a.age = age
    w.add(a)
    return a


def _world(clock_on=True, tick=10):
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    w.clock_enabled = clock_on
    w.tick = tick
    return w


def test_night_pauses_labour_but_never_bellies():
    w = _world(tick=75)                            # deep night
    a = _soul(w, "s0", "Vesper")
    a.stores, before = 1.0, 1.0
    w.commons = 0.0
    stakes.step(w)
    assert a.stores < before                       # the belly ran (consumption)
    assert not hasattr(a, "_last_action") or a._last_action is None \
        or a._last_action == getattr(a, "_last_action")  # no crash path
    assert getattr(a, "_last_action", None) is None      # ...but nobody laboured


def test_harvest_feeds_and_winter_bites():
    def yield_of(tick):
        w = _world(tick=tick)
        a = _soul(w, "s0", "Mara")
        w.commons = 0.0
        stakes.apply_action(a, "work", w, w.tick)
        return w.commons
    harvest = yield_of(17 * 100 + 10)              # harvest, daytime
    winter = yield_of(25 * 100 + 10)               # winter, daytime
    assert harvest > winter > 0                    # the season is REAL in the granary


def test_the_turn_of_season_is_felt_once():
    w = _world(tick=799)                           # the last tick of spring (8 days x 100)
    a = _soul(w, "s0", "Cael")
    w._last_season = "spring"
    for t in range(800, 803):
        w.tick = t
        w._clock_tick()
    turns = [m for m in a.memory.items if m.lore_id.startswith("season:")]
    assert len(turns) == 1                         # one turn, one memory -- not three
    assert "long days" in turns[0].text            # summer arrived, and it was felt


def test_children_play_eat_little_and_cannot_starve_out():
    w = _world(tick=10)
    child = _soul(w, "s0", "Little", lifespan=1000, age=50)     # 5% of a life: a child
    adult = _soul(w, "s1", "Grown", lifespan=1000, age=300)
    child.metabolism = adult.metabolism = 0.5
    w.selection_enabled = True
    w.heredity_enabled = True
    # a famine: nothing anywhere, for everyone
    for t in range(11, 260):
        w.tick = t
        child.stores = adult.stores = 0.0
        w.commons = 0.0
        stakes.step(w)
        assert getattr(child, "_last_action", "tend") == "tend"   # children play and learn
        w._selection_tick()
        if adult not in w.agents:
            break
    assert adult not in w.agents                   # famine took the grown
    assert child in w.agents                       # the hazard never opens on a child


def test_elders_tire_but_keep_the_legends():
    w = _world(tick=10)
    elder = _soul(w, "s0", "Old", lifespan=1000, age=900)
    adult = _soul(w, "s1", "Young", lifespan=1000, age=300)
    w.commons = 0.0
    stakes.apply_action(elder, "work", w, w.tick)
    elder_yield = w.commons
    w.commons = 0.0
    stakes.apply_action(adult, "work", w, w.tick)
    assert w.commons > elder_yield                 # labour tires the old
    legend = elder.memory.write("they say the weir took a fisher the year the water rose",
                                tick=10, source="lore", lore_id="ev:9")
    legend.salience = 0.05                         # decayed nearly to forgetting
    w._clock_tick()
    assert legend.salience >= clock.ELDER_LORE_FLOOR   # the old remember the old stories


def test_the_gate_defaults_off_and_old_snapshots_wake():
    assert World().clock_enabled is False
    w = _world(clock_on=False, tick=75)            # "night" -- but there is no night
    a = _soul(w, "s0", "Vesper")
    stakes.step(w)
    assert getattr(a, "_last_action", None) is not None   # clockless towns work all hours
    state = _world().__getstate__()
    for k in ("clock_enabled", "day_ticks", "_last_season"):
        del state[k]
    w2 = object.__new__(World)
    w2.__setstate__(state)
    assert w2.clock_enabled is False and w2.day_ticks == 100   # THE RULE


def test_the_town_roams_in_relationship_knots_with_state_gaits():
    """Big-town drift: bonded souls converge (knots roam together), the restless
    outpace the weary, and night stills every body."""
    import math
    import random as _r
    from agent.bond import Bond
    from world import clock as _clock

    w = _world(clock_on=False)               # clock joins later, for the night check
    rng = _r.Random(3)
    for i in range(60):                      # > 48: the sampled big-town path
        a = _soul(w, f"s{i}", f"F{i}")
        a.position = (rng.uniform(0, 900), rng.uniform(0, 600))
        a.arousal = 0.3
        a.bond_enabled = True
    w.move_enabled = True
    w.bounds = (900, 600)
    a0, a1 = w.agents[0], w.agents[1]
    a0.position, a1.position = (100.0, 100.0), (800.0, 500.0)
    a0.bonds["s1"] = Bond(trust=0.9, history=3.0)
    a1.bonds["s0"] = Bond(trust=0.9, history=3.0)
    d_before = math.dist(a0.position, a1.position)
    restless, weary = w.agents[2], w.agents[3]
    restless.arousal, restless.wellbeing = 1.0, 1.0
    weary.arousal, weary.wellbeing = 0.0, 0.05
    pr, pw = restless.position, weary.position
    for _ in range(150):
        w._drift_positions()
    assert math.dist(a0.position, a1.position) < d_before      # the bond is a road
    assert math.dist(restless.position, pr) > math.dist(weary.position, pw)
    # and night stills the body: step() at night must not move anyone
    w.clock_enabled = True
    w.tick = int(w.day_ticks * 0.8)                             # deep night
    assert _clock.is_night(w.tick, w.day_ticks)
    frozen = [a.position for a in w.agents]
    with w.lock:
        w.step(speak=False)
    assert [a.position for a in w.agents] == frozen
