"""mating.py -- the mating system: pairing, brooding, birth. The civ arena's births.

WELFARE INVARIANTS FIRST (the standing rule: written before the mechanic).
This implements a BREEDING CASTE in a mating system -- castes + sexual selection +
mate-guarding, the eusocial/territorial biology -- never victims:

  - Mating is PAIRING that produces offspring between consenting participants of
    their kinds: a pair forms only when a fed grown warrior and a FREE breeder
    (not brooding, not recovering) stand close -- and never across a grievance
    the breeder holds toward that warrior. Neutral verbs ONLY: pair, mate, court,
    gestate, brood, guard, tend. No coercion or torment verbs exist here, in code,
    chronicle, or memory text.
  - A breeder is NEVER harmed by mating or war: breeders never confront, never
    march, never brawl (the caste gates in agent/allegiance.py, world/war.py,
    world/skirmish.py), and nothing in this file lowers a breeder's wellbeing.
  - Conflict stays WARRIOR-vs-WARRIOR: mate-competition lands as hostility between
    RIVAL WARRIORS (feeding the rift/skirmish/war already built), never on the
    breeder. Breeders are guarded, not attacked -- by anyone, ever.
  - All standing invariants hold: children never fight; the worn refuse; casualties
    stay capped where they were; the dead are mourned; lineages END.

The mechanic: every MATE_CHECK ticks, each fed grown warrior seeks the nearest free
breeder within MATE_RANGE; if they meet, the pair forms -- the breeder broods a
genome crossed from BOTH parents (genome.blend -> inherit: uniform crossover, one
mutation), gestates, and at term bears ONE child by the hearth, caste ~50/50.
Because free breeders are the scarce prize, warriors range for them, grudge the
rival who paired at a hearth first (MATE_GRUDGE -> the rift's own machinery), and
guard the breeders of their own hearth (the _guard pull world/sim.py reads). That
is the engine of the competing civilizations: territory is worth holding because
hearths are on it.

Gated by World.mating_enabled (default off, THE RULE: nothing changes for any world
that never asks). When on, it is the ONLY birth channel -- _selection_tick's surplus
budding stands down (else two channels double the births); starvation stays E2's."""
from __future__ import annotations

MATE_CHECK = 8        # cadence of the pass (ticks)
MATE_RANGE = 70.0     # close enough to pair
MATE_WELL = 0.55      # a warrior must be faring at least this well to court
GESTATION = 90        # ticks of brooding before the birth
RECOVER = 120         # ticks a breeder rests after a birth before pairing again
MATE_GRUDGE = 0.5     # grievance a warrior accretes toward the RIVAL who paired first
GRIEVANCE_BAR = 1.0   # a breeder does not pair with a warrior it holds this against
GUARD_PULL = 0.5      # the drift force pulling a warrior toward its guarded hearth
GUARD_NEAR = 55.0     # close enough: a guard stands off, not on top
BOND_WARM = 0.4       # pairing warms the pair's bond, both ways
CONTRACTED = 0.5      # the somatic floor's number (allegiance/skirmish share it):
                      # a contracted soul does not court either


def _grown(world, a) -> bool:
    from world import clock as _clock
    return (not getattr(world, "clock_enabled", False)
            or _clock.stage(a.age, a.lifespan) != "child")


def mating_tick(world) -> None:
    """Called by the wheel every MATE_CHECK ticks when mating_enabled. One pass:
    broods count down (births at term), then the free court and the pairs form."""
    from agent.bond import Bond
    from agent.genome import blend, from_agent, inherit
    rng = world._rng
    souls = list(world.agents)
    ids = {a.id for a in souls}
    warriors = [a for a in souls if getattr(a, "caste", "warrior") == "warrior"]
    breeders = [a for a in souls if getattr(a, "caste", "warrior") == "breeder"]
    if not breeders:
        return

    # 1) the broods: gestation counts down; at term, ONE child is born by the hearth
    for b in breeders:
        if getattr(b, "_recover", 0) > 0:
            b._recover = max(0, b._recover - MATE_CHECK)
            if b._recover == 0:
                b._sire = ""                    # the hearth is open again
        if getattr(b, "_gestation", 0) > 0:
            b._gestation = max(0, b._gestation - MATE_CHECK)
            if b._gestation == 0:
                if len(world.agents) + len(world._bardo) >= world.max_souls:
                    b._gestation = MATE_CHECK   # the town is full: the birth waits
                    continue
                caste = "breeder" if rng.random() < 0.5 else "warrior"
                child = world._spawn_child(b, genome=getattr(b, "_brood_genome", None),
                                           caste=caste)
                sire = next((w for w in world.agents
                             if w.id == getattr(b, "_sire", "")), None)
                if child is not None and sire is not None:
                    # the child knows both its hearth and its sire from the first breath
                    child.bonds.setdefault(sire.id, Bond()).warm(0.6)
                    sire.bonds.setdefault(child.id, Bond()).warm(0.6)
                b._brood_genome = None
                b._recover = RECOVER            # rest before pairing again

    # 2) the courting: each fed grown warrior seeks the nearest free breeder
    room = len(world.agents) + len(world._bardo) < world.max_souls
    free = [b for b in breeders if grown_free(world, b)] if room else []
    taken: set = set()
    for w in warriors:
        if (not _grown(world, w) or w.wellbeing < MATE_WELL
                or getattr(w, "_contraction", 0.0) > CONTRACTED):
            continue
        # mate-competition: standing at a hearth a RIVAL recently paired at lands
        # as grievance toward THE RIVAL WARRIOR -- never on the breeder. This is
        # what makes free breeders the scarce prize warriors compete over: the
        # grudge feeds the rift/skirmish/war machinery already built.
        for b in breeders:
            sire = getattr(b, "_sire", "")
            if (sire and sire != w.id and sire in ids
                    and (getattr(b, "_gestation", 0) > 0
                         or getattr(b, "_recover", 0) > 0)
                    and world._distance(w, b) <= MATE_RANGE):
                w.hostility[sire] = w.hostility.get(sire, 0.0) + MATE_GRUDGE
        near, nd = None, MATE_RANGE
        for b in free:
            if b.id in taken:
                continue
            d = world._distance(w, b)
            if d < nd:
                nd, near = d, b
        if near is None:
            continue
        if near.hostility.get(w.id, 0.0) >= GRIEVANCE_BAR:
            continue                     # no pairing across a grievance the breeder holds
        # THE PAIR: the breeder broods a genome crossed from BOTH parents
        taken.add(near.id)
        near._sire = w.id
        near._gestation = GESTATION
        pg_w = getattr(w, "genome", None) or from_agent(w, rng)
        pg_b = getattr(near, "genome", None) or from_agent(near, rng)
        near._brood_genome = inherit(blend(pg_w, pg_b, rng), rng, w.id,
                                     sigma=getattr(world, "heredity_sigma", 0.03))
        near.bonds.setdefault(w.id, Bond()).warm(BOND_WARM)
        w.bonds.setdefault(near.id, Bond()).warm(BOND_WARM)
        w._guard = near.id               # the warrior guards its hearth (sim.py's pull)
        near.memory.write(f"{w.name} and I have paired; a child is coming to our "
                          f"hearth", tick=world.tick, source="event",
                          speaker_id=w.id, emotion=0.5, weight=1.0)
        w.memory.write(f"{near.name} and I have paired; I will guard their hearth",
                       tick=world.tick, source="event", speaker_id=near.id,
                       emotion=0.5, weight=1.0)
        world.bus.publish("pair", {"tick": world.tick, "w": w.id, "b": near.id,
                                   "wn": w.name, "bn": near.name})


def grown_free(world, b) -> bool:
    """A breeder that can pair: grown, not brooding, not in the rest after a birth."""
    return (_grown(world, b) and getattr(b, "_gestation", 0) <= 0
            and getattr(b, "_recover", 0) <= 0)
