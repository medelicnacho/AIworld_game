"""Tests for floored-wound erosion (agent/memory.py) and the hearth cap (world/sim.py).

The leak these bound: a floored memory's salience never decays below its floor, and
FORGET_THRESHOLD (0.08) sits far under a grievance floor (0.5) -- so a floored memory can
NEVER be pruned. World._hearth then copies every floored memory a parent holds into each
child, so grievances REPLICATE down the generations. Measured over 24k ticks: floored items
went from 0.4% of all memory to 57.6%, still climbing.
"""

import pytest

from agent.memory import FLOOR_EROSION, FORGET_THRESHOLD, MemoryStore


def _store(forgiveness=0.0):
    m = MemoryStore(seed=1)
    m.forgiveness = forgiveness
    return m


def test_off_by_default_the_floor_is_immovable():
    """THE RULE: forgiveness 0 is the default and reproduces the old behaviour exactly --
    §5.28's feud persistence was measured on it."""
    m = _store()
    wound = m.write("they burned our granary", tick=0, source="event", salience_floor=0.5)
    for t in range(1, 3000):
        m.tick(t)
    assert wound.salience_floor == 0.5
    assert wound.salience >= 0.5
    assert wound in m.items          # never pruned, however long it runs


def test_time_alone_eventually_lets_a_dead_wound_close():
    m = _store(forgiveness=0.0001)    # nonzero but tiny: time, essentially no warmth
    wound = m.write("they burned our granary", tick=0, source="event", salience_floor=0.5)
    for t in range(1, 6000):
        m.tick(t)
    # NB it never reaches floor 0: salience tracks the descending floor down and is culled
    # the moment that floor passes under FORGET_THRESHOLD. Being FORGETTABLE is the claim.
    assert wound.salience_floor < FORGET_THRESHOLD
    assert wound not in m.items       # prunable again, and pruned


def test_warmth_buries_a_wound_faster_than_time():
    def survive(forgiveness, ticks=1500):
        m = _store(forgiveness)
        w = m.write("they burned our granary", tick=0, source="event", salience_floor=0.5)
        for t in range(1, ticks):
            m.tick(t)
        return w.salience_floor
    cold = survive(0.0001)      # a soul among enemies
    warm = survive(1.0)         # a soul among friends
    assert warm < cold
    assert warm == 0.0          # full warmth closes it inside ~one lifetime


def test_an_ACTIVE_feud_is_untouched():
    """The design line: this ends DEAD feuds, not live ones. war.py rewrites the grievance
    and lore.py's retellings carry the floor -- both restore it faster than erosion."""
    m = _store(forgiveness=1.0)              # maximum warmth: the hardest case for this
    for t in range(0, 4000, 120):            # the feud keeps being renewed
        m.write("they burned our granary", tick=t, source="event", salience_floor=0.5)
        for u in range(t + 1, t + 120):
            m.tick(u)
    # the claim is about the MIND, not one object: text mutation means a renewal may merge
    # into a blurred copy or land as a fresh memory, so chasing one Memory is fragile.
    assert m.holds_floored()
    assert max(x.salience_floor for x in m.items) > 0.3   # a live wound stays a wound


def test_erosion_rate_is_slower_than_a_lifetime():
    """A grievance must outlast its holder, or a feud can never cross a generation at all
    (which would break §5.28's G2). A soul lives ~900-1400 ticks."""
    assert 0.5 / FLOOR_EROSION > 3000


def test_holds_floored_is_accurate_and_cheap():
    m = _store()
    assert not m.holds_floored()
    m.write("an ordinary day", tick=0, source="event")
    assert not m.holds_floored()
    m.write("they burned our granary", tick=0, source="event", salience_floor=0.5)
    assert m.holds_floored()


def test_holds_floored_clears_once_the_wound_closes():
    m = _store(forgiveness=1.0)
    m.write("they burned our granary", tick=0, source="event", salience_floor=0.5)
    assert m.holds_floored()
    for t in range(1, 3000):
        m.tick(t)
    assert not m.holds_floored()      # the counter is resynced by the prune pass


def test_hearth_cap_limits_what_a_child_inherits():
    """The replication term: uncapped, every birth copies the parent's whole grievance
    ledger. Capped, a child is raised on the house's LOUDEST wounds only."""
    from agent.agent import Agent
    from services.llm import MockLLM
    from world.sim import World

    def child_of(parent_wounds, cap):
        w = World(rebirth_enabled=False, events_enabled=False, move_seed=1)
        w.hearth_carry = cap
        parent = Agent("p", "P", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
        child = Agent("c", "C", (0, 0), "p", ["x"], MockLLM(seed=2), seed=2)
        for i in range(parent_wounds):
            m = parent.memory.write(f"wound number {i}", tick=0, source="event",
                                    salience_floor=0.5)
            m.salience = 0.3 + i * 0.05        # distinct loudness, so "top K" is defined
        w._hearth(parent, child)
        return [m for m in child.memory.items
                if getattr(m, "salience_floor", 0.0) > 0.0]

    assert len(child_of(8, 0)) == 8        # uncapped: the whole ledger crosses (the default)
    assert len(child_of(8, 3)) == 3        # capped: three only
    assert len(child_of(2, 3)) == 2        # fewer wounds than the cap: all of them


def test_the_cap_keeps_the_LOUDEST_wounds():
    """§5.16's legend dynamics and §5.28's G2 both ride on the strongest stories, so those
    are exactly the ones a cap must keep."""
    from agent.agent import Agent
    from services.llm import MockLLM
    from world.sim import World
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=1)
    w.hearth_carry = 2
    parent = Agent("p", "P", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    child = Agent("c", "C", (0, 0), "p", ["x"], MockLLM(seed=2), seed=2)
    for i, sal in enumerate((0.2, 0.9, 0.3, 0.8)):
        m = parent.memory.write(f"wound {i}", tick=0, source="event", salience_floor=0.5)
        m.salience = sal
    w._hearth(parent, child)
    kept = {m.text for m in child.memory.items
            if getattr(m, "salience_floor", 0.0) > 0.0}   # its own doctrine is unfloored
    assert kept == {"wound 1", "wound 3"}      # the 0.9 and the 0.8


# --- the closed-form fast-forward (gameworld PLAN §3 consequence 2) ------------------
# A settlement the player left 40,000 ticks ago must catch up in microseconds AND have
# genuinely aged, or "the world lives while you're away" is a lie. The plan states it as
# `salience = max(s · decay^Δt, floor)`, which was exact while the floor was immovable and
# is NOT once forgiveness erodes it. These pin the replacement against literal ticking --
# the only test that matters for a closed form is that it equals the thing it replaces.

def _ticked(s, floor, decay, erosion, dt):
    """The ground truth: what MemoryStore.tick() does to one memory, dt times."""
    for _ in range(dt):
        if erosion and floor > 0:
            floor = max(0.0, floor - erosion)
        s = max(s * decay, floor)
    return s, floor


@pytest.mark.parametrize("eff", (0.0, 0.5, 1.0))
@pytest.mark.parametrize("warmth", (0.0, 0.25, 1.0))
@pytest.mark.parametrize("dt", (1, 2, 50, 1000, 40000))
def test_closed_form_equals_ticking(eff, warmth, dt):
    from agent.memory import FLOOR_EROSION, FORGIVE_GAIN
    decay = 0.97 + 0.025 * eff
    erosion = FLOOR_EROSION * (1.0 + FORGIVE_GAIN * warmth) if warmth > 0 else 0.0
    for s0 in (1.0, 0.6, 0.12, 0.02):
        for f0 in (0.0, 0.05, 0.24, 0.5, 0.9):
            got = MemoryStore._advance(s0, f0, decay, erosion, dt)
            want = _ticked(s0, f0, decay, erosion, dt)
            assert abs(got[0] - want[0]) < 1e-9, (s0, f0, dt, got, want)
            assert abs(got[1] - want[1]) < 1e-9, (s0, f0, dt, got, want)


def test_closed_form_handles_a_memory_starting_BELOW_its_floor():
    """A floor RAISED by a retelling leaves salience under it -- the memory is pinned from
    tick zero. Two bisection attempts both got this wrong (7.2e-03 and 7.4e-04 too low),
    because the predicate they searched is not monotonic in that case."""
    got = MemoryStore._advance(0.02, 0.05, 0.995, 0.0012, 1)
    want = _ticked(0.02, 0.05, 0.995, 0.0012, 1)
    assert abs(got[0] - want[0]) < 1e-9


def test_fast_forward_matches_a_real_run_on_a_whole_store():
    """End to end, mutation off so text is deterministic: a store fast-forwarded 5000
    ticks must hold the same memories, at the same salience, as one that lived them."""
    import agent.memory as mem
    old_chance = mem.MUTATE_CHANCE
    mem.MUTATE_CHANCE = 0.0
    try:
        def build():
            m = MemoryStore(seed=3)
            m.forgiveness = 0.5
            for i, (txt, fl) in enumerate((("an ordinary day", 0.0),
                                           ("they burned our granary", 0.5),
                                           ("a quiet season", 0.0),
                                           ("the old wound", 0.2))):
                m.write(txt, tick=0, source="event", salience_floor=fl)
            return m
        lived, jumped = build(), build()
        for t in range(1, 5001):
            lived.tick(t)
        jumped.fast_forward(5000, now=5000)
        assert len(lived.items) == len(jumped.items)
        for a, b in zip(sorted(lived.items, key=lambda x: x.text),
                        sorted(jumped.items, key=lambda x: x.text)):
            assert a.text == b.text
            assert abs(a.salience - b.salience) < 1e-9
            assert abs(a.salience_floor - b.salience_floor) < 1e-9
        assert lived.holds_floored() == jumped.holds_floored()
    finally:
        mem.MUTATE_CHANCE = old_chance


def test_fast_forward_is_independent_of_dt():
    """O(items), not O(dt): the whole point. 40,000 ticks must cost what 10 does."""
    import time
    def cost(dt):
        m = MemoryStore(seed=1)
        for i in range(200):
            m.write(f"memory {i}", tick=0, source="event",
                    salience_floor=0.5 if i % 3 == 0 else 0.0)
        t0 = time.perf_counter()
        m.fast_forward(dt, now=dt)
        return time.perf_counter() - t0
    cost(10)                                    # warm
    assert cost(40000) < cost(10) * 5 + 0.05    # generous: it must not scale with dt
