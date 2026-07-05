"""Tests for war (world/war.py) -- raids over lean granaries.

Pinned: hunger beside a fat granary raids and moves real food; fed folk never march;
grievances land on every defender-bloc soul with the charge IN THE WORDS and a
land-keyed feud tag; hostility hardens toward the raiders; the dead are mourned by
their bonded and their lineages END (no bardo); the worn refuse the march (the
somatic floor extends to war); and casualties respect the cap."""

import random

from agent.agent import Agent
from agent.bond import Bond
from agent.memory import valence
from services.llm import MockLLM
from world import factions as F
from world import regions as R
from world import war
from world.sim import World


def _eco(seed=5):
    """Two blocs on two grounds: the crag-folk (region argmin soil) hungry beside the
    vale-folk (argmax) with a fat pool."""
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    w._rng = random.Random(seed)
    w.regions_enabled = True
    w.regions = R.Regions(seed=1)
    w.war_enabled = True
    rich = max(range(6), key=lambda i: w.regions.yields[i])
    poor = min(range(6), key=lambda i: w.regions.yields[i])
    cx = lambda i: ((i % R.COLS) * 300 + 150.0, (i // R.COLS) * 300 + 150.0)
    souls = []
    for i in range(8):
        atk = i < 4
        a = Agent(f"s{i}", f"{'K' if atk else 'V'}{i}", cx(poor if atk else rich),
                  "You are a soul.", ["the well"], w.llm, seed=i,
                  temperament=0.0, lifespan=10 ** 6)
        a.bond_enabled = True
        a.boldness = 0.9 if atk else 0.4
        a.belief_vec = (1.0, 0, 0, 0, 0, 0) if atk else (-1.0, 0, 0, 0, 0, 0)
        w.add(a)
        souls.append(a)
    # deep in-bloc trust so the muster actually raises a party
    for a in souls[:4]:
        for b in souls[:4]:
            if a is not b:
                a.bonds[b.id] = Bond(trust=0.8, history=2.5)
    for a in souls[4:]:
        for b in souls[4:]:
            if a is not b:
                a.bonds[b.id] = Bond(trust=0.8, history=2.5)
    w.regions.pools = [0.0] * 6
    w.regions.pools[rich] = 6.0                    # the vale groans; the crag is bare
    return w, rich, poor, souls


def test_hunger_marches_and_food_moves():
    w, rich, poor, souls = _eco()
    before = w.regions.pools[rich]
    war.war_tick(w)
    assert w._war_log, "a raid should have happened"
    log = w._war_log[-1]
    assert log["atk"] == poor and log["dfd"] == rich
    if log["won"]:
        assert w.regions.pools[rich] < before      # real food moved
        assert w.regions.pools[poor] > 0
    assert len(log["fallen"]) <= war.CASUALTY_CAP


def test_grievance_lands_worded_and_land_keyed():
    w, rich, poor, souls = _eco()
    war.war_tick(w)
    feud = f"feud:{poor}>{rich}"
    griefs = [m for a in souls[4:] if a in w.agents
              for m in a.memory.items if m.lore_id == feud and m.emotion < -0.5]
    assert griefs, "every defender bloc soul carries the grievance"
    assert all(valence(m.text) < 0 for m in griefs)    # the charge is IN the words
    # hostility hardened toward the raiders
    party = set(w._war_log[-1]["party"])
    assert any(a.hostility.get(pid, 0) > 0 for a in souls[4:] if a in w.agents
               for pid in party)


def test_the_dead_end_and_are_mourned():
    w, rich, poor, souls = _eco(seed=9)
    n0 = len(w.agents)
    war.war_tick(w)
    fallen = w._war_log[-1]["fallen"]
    if fallen:                                     # deaths are stochastic but capped
        assert len(w.agents) == n0 - len(fallen)   # lineages END -- no bardo
        assert len(w._bardo) == 0
        mourned = [m for a in w.agents for m in a.memory.items
                   if any(name in m.text for name in fallen) and m.emotion < 0]
        assert mourned                             # someone bonded carries the loss


def test_fed_folk_never_march_and_the_worn_refuse():
    w, rich, poor, souls = _eco()
    w.regions.pools[poor] = 10.0                   # the crag eats well tonight
    war.war_tick(w)
    assert not w._war_log                          # no hunger, no war
    w.regions.pools[poor] = 0.0
    souls[1].wellbeing = 0.08                      # too worn for any march
    war.war_tick(w)
    assert w._war_log and "s1" not in w._war_log[-1]["party"]


def test_grievance_never_decays_and_the_floor_travels():
    """G2's seam: a grievance is floored (the wound that will not close) so decay
    cannot forget it, and a RETELLING writes the hearer's copy with the same floor
    -- the feud stays keepable in souls who never fought the raid that made it."""
    from agent import lore
    from agent.agent import Agent
    w, rich, poor, souls = _eco()
    war.war_tick(w)
    assert w._war_log
    feud = f"feud:{poor}>{rich}"
    victim = next(a for a in souls[4:] if a in w.agents
                  and any(m.lore_id == feud for m in a.memory.items))
    g = next(m for m in victim.memory.items if m.lore_id == feud)
    assert g.salience_floor == war.GRIEVANCE_FLOOR
    for t in range(3000):                          # years of peace gnaw at it...
        victim.memory.tick(now=10_000 + t)
    kept = [m for m in victim.memory.items if m.lore_id == feud]
    assert kept and kept[0].salience >= war.GRIEVANCE_FLOOR   # ...and it holds
    # a soul born long after the raid hears the story -- floored, like the original
    born = Agent("later", "Later", victim.position, "You are a soul.",
                 ["the well"], w.llm, seed=99, temperament=0.0, lifespan=10 ** 6)
    w.add(born)
    w.lore_enabled = True
    for _ in range(400):                           # cooldowns stagger the telling
        lore.retell(w)
    theirs = [m for m in born.memory.items if m.lore_id == feud]
    assert theirs, "the feud reached the unborn"
    assert theirs[0].salience_floor == war.GRIEVANCE_FLOOR


def test_the_hearth_hands_the_wound_to_the_newborn():
    """The hearth (G2's second seam): a floored grievance crosses AT BIRTH, in the
    words the parent currently carries -- the square's retell lottery is not the
    only channel, so generation three hears the feud even in a town that mourns
    louder than it remembers. Provenance stays honest: source='lore', a story."""
    w, rich, poor, souls = _eco()
    war.war_tick(w)
    assert w._war_log
    feud = f"feud:{poor}>{rich}"
    victim = next(a for a in souls[4:] if a in w.agents
                  and any(m.lore_id == feud for m in a.memory.items))
    victim.stores = 5.0                            # provisioned enough to give birth
    w._birth_from(victim)
    child = w.agents[-1]
    assert child.id.startswith("born:")
    got = [m for m in child.memory.items if m.lore_id == feud]
    assert got, "the wound crossed at birth"
    assert got[0].salience_floor == war.GRIEVANCE_FLOOR
    assert got[0].source == "lore"                 # a story received, not lived


def test_ally_children_never_march():
    """The welfare rule holds for ALLIES too: a third bloc that stands with the
    defenders sends only its grown -- its children stay home (this filter was
    missing; an ally's child could be mustered and fall)."""
    from agent.agent import Agent
    from agent.bond import Bond
    w, rich, poor, souls = _eco()
    w.clock_enabled = True
    for a in souls:
        a.age = int(0.5 * a.lifespan)              # the two blocs are grown folk
    third = min((i for i in range(6) if i not in (rich, poor)),
                key=lambda i: abs(i - rich))
    cx = lambda i: ((i % R.COLS) * 300 + 150.0, (i // R.COLS) * 300 + 150.0)
    ally = []
    for j in range(4):
        a = Agent(f"al{j}", f"A{j}", cx(third), "You are a soul.", ["the well"],
                  w.llm, seed=50 + j, temperament=0.0, lifespan=10 ** 6)
        a.bond_enabled = True
        a.boldness = 0.9
        # leaning toward the defenders (BELOW the same-bloc line, so they remain a
        # distinct third bloc), against the attackers -> they stand with them
        a.belief_vec = (-0.3, (1 - 0.09) ** 0.5, 0.0, 0.0, 0.0, 0.0)
        a.age = 0 if j == 3 else int(0.5 * a.lifespan)   # al3 is a CHILD
        w.add(a)
        ally.append(a)
    for a in ally:
        for b in ally:
            if a is not b:
                a.bonds[b.id] = Bond(trust=0.8, history=2.5)
    war.war_tick(w)
    assert w._war_log, "the raid still happens"
    dfd_ids = set(w._war_log[-1]["defenders"])
    assert any(a.id in dfd_ids for a in ally[:3]), "grown allies joined the defence"
    assert "al3" not in dfd_ids, "the ally's child stayed home"
