"""Tests for skirmishes (world/skirmish.py) and the rift (agent.py) -- the
civilization game's collapse channel: debate becomes enmity, enmity becomes blows.

Pinned: the gate defaults OFF (and old snapshots wake with it off -- THE RULE); the
angry CLOSE on their enemies and a clash hurts both, hardens the grudge both ways, and
writes charged land-keyed memories; children never fight; the worn disengage and are
unreachable; deaths are capped, mourned, and END the lineage (no bardo); the rift
builds hostility from deeply opposed heard opinions ONLY when rift_enabled."""

import random

from agent.agent import RIFT_AT, WAR_THRESHOLD, Agent
from agent.bond import Bond
from services.llm import MockLLM
from world import skirmish
from world.events import Utterance
from world.sim import World


def _pair(seed=3, d=120.0, well=(1.0, 1.0), hostile=True):
    """Two grown souls d apart; mutual open enmity unless hostile=False."""
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    w._rng = random.Random(seed)
    w.skirmish_enabled = True
    a = Agent("s0", "Ash", (100.0, 100.0), "You are a soul.", ["the well"],
              w.llm, seed=1, temperament=0.0, lifespan=10 ** 6)
    b = Agent("s1", "Bram", (100.0 + d, 100.0), "You are a soul.", ["the well"],
              w.llm, seed=2, temperament=0.0, lifespan=10 ** 6)
    a.wellbeing, b.wellbeing = well
    a.boldness, b.boldness = 0.8, 0.6
    if hostile:
        a.hostility["s1"] = WAR_THRESHOLD
        b.hostility["s0"] = WAR_THRESHOLD
    w.add(a)
    w.add(b)
    return w, a, b


def test_gate_defaults_off_everywhere():
    w = World(events_enabled=False)
    assert w.skirmish_enabled is False
    state = w.__getstate__()
    state.pop("skirmish_enabled", None)            # a pre-skirmish snapshot
    w2 = object.__new__(World)
    w2.__setstate__(state)
    assert w2.skirmish_enabled is False            # THE RULE: defaults, never a freeze
    assert Agent("x", "X", (0, 0), "p", ["m"], MockLLM(seed=1),
                 seed=1).rift_enabled is False


def test_the_angry_close_and_come_to_blows():
    w, a, b = _pair()
    hits = []
    w.bus.subscribe("skirmish", hits.append)
    d0 = w._distance(a, b)
    skirmish.skirmish_tick(w)
    assert w._distance(a, b) < d0                  # the angry go to each other
    for _ in range(40):
        skirmish.skirmish_tick(w)
        if hits:
            break
    assert hits, "the quarrel came to blows"
    assert a.wellbeing < 1.0 and b.wellbeing < 1.0     # a clash costs BOTH
    assert a.hostility["s1"] > WAR_THRESHOLD           # and deepens the grudge
    assert b.hostility["s0"] > WAR_THRESHOLD
    assert any("came to blows" in m.text for m in a.memory.items)
    assert any(m.lore_id.startswith("brawl:") for m in b.memory.items)


def test_children_never_fight():
    w, a, b = _pair(d=10.0)                        # already at arm's length
    w.clock_enabled = True
    a.age = int(0.5 * a.lifespan)                  # grown and furious
    b.age = 0                                      # a child
    before = b.wellbeing
    for _ in range(10):
        skirmish.skirmish_tick(w)
    assert b.wellbeing == before                   # no verb reaches a child
    b.age = int(0.5 * b.lifespan)
    skirmish.skirmish_tick(w)
    assert b.wellbeing < before                    # grown, the same quarrel lands


def test_the_worn_disengage_and_are_unreachable():
    w, a, b = _pair(d=10.0, well=(1.0, 0.2))       # Bram is collapsed (< 0.25)
    before = b.wellbeing
    d0 = w._distance(a, b)
    for _ in range(6):
        skirmish.skirmish_tick(w)
    assert b.wellbeing == before                   # the worn are unreachable
    assert w._distance(a, b) > d0                  # and they step away from it all


def test_deaths_capped_mourned_and_lineages_end():
    # both still FIT to stand (>= the somatic floor) -- and one clash beats the
    # loser below the edge: the fall happens IN the blow, never to the worn
    w, a, b = _pair(d=10.0, well=(0.3, 0.3))
    w.mourning_enabled = True
    o = Agent("s2", "Orla", (400.0, 400.0), "You are a soul.", ["the well"],
              w.llm, seed=3, temperament=0.0, lifespan=10 ** 6)
    o.bond_enabled = True
    o.bonds["s0"] = Bond(trust=0.8, history=2.0)
    o.bonds["s1"] = Bond(trust=0.8, history=2.0)
    w.add(o)
    deaths = []
    w.bus.subscribe("skirmish_death", deaths.append)
    skirmish.skirmish_tick(w)
    assert len(deaths) == 1                        # both at the edge; the cap holds
    assert len(w.agents) == 2 and len(w._bardo) == 0   # the lineage ENDS, no bardo
    assert any(m.emotion < 0 and "gone" in m.text for m in o.memory.items)


def test_solidarity_warms_those_who_share_the_quarrel():
    """The muster's fuel: a witness who shares the grievance warms toward the one
    who stood in the brawl -- out-group conflict cements in-group trust, so an
    EMERGENT camp can eventually raise a war party (no bonds are ever pre-seeded)."""
    w, a, b = _pair(d=10.0)
    w.hearing_range = 300.0
    c = Agent("s2", "Cole", (120.0, 100.0), "You are a soul.", ["the well"],
              w.llm, seed=4, temperament=0.0, lifespan=10 ** 6)
    c.bond_enabled = True
    c.hostility["s1"] = skirmish.SOLIDARITY_MIN    # Cole shares Ash's quarrel with Bram
    w.add(c)
    for _ in range(10):
        skirmish.skirmish_tick(w)
        if any(m.lore_id.startswith("brawl:") for m in a.memory.items):
            break
    assert c.bonds.get("s0") is not None and c.bonds["s0"].trust > 0, \
        "the one who stood against Bram earned Cole's trust"
    assert c.bonds.get("s1") is None or c.bonds["s1"].trust <= 0


def test_rift_builds_hostility_only_when_enabled():
    w, a, b = _pair(hostile=False)
    a.belief_vec = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    opposed = Utterance(speaker_id="s1", text="no", tick=1, source="ai",
                        belief_vec=(-1.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    a.hear(opposed, now=1)
    assert a.hostility.get("s1", 0.0) == 0.0       # rift off: chill, never grievance
    a.rift_enabled = True
    n = 0
    while a.hostility.get("s1", 0.0) < WAR_THRESHOLD and n < 50:
        a.belief_vec = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)   # a held conviction, re-argued
        a.hear(opposed, now=2 + n)
        n += 1
    assert n > 1, "one exchange must NOT make an enemy"
    assert a.hostility["s1"] >= WAR_THRESHOLD      # debate after debate does
    assert abs(RIFT_AT) < 1.0                      # the rift bound is a real cosine
