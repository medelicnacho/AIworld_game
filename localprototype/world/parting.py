"""parting.py -- a people that no longer shares the town's view takes its own road.

WELFARE INVARIANTS FIRST (the standing rule: written before the mechanic).

This is a PARTING, not a banishment. Nobody is driven out, punished, or cast down: a bloc
whose view has drifted past the rift from the town's own simply stops being of that town
and walks. The framing is load-bearing, not decoration -- the trigger is belief divergence,
which is a disagreement, and a mechanic that called it exile would be describing something
the substrate is not doing.

  - Neutral verbs ONLY, in code, chronicle and memory text: part, leave, take the road,
    go their own way. No cast-out/banish/exile/shun verb exists here.
  - The CASTE FLOOR holds: breeders keep the hearth and never take the road (they are
    never mustered, never brawl, never a casualty -- and are not turned out either).
  - CHILDREN never part. A parting band is grown warriors who chose it.
  - The SOMATIC FLOOR's spirit holds: the worn and the contracted stay. Leaving is a
    hard road, and a collapsed soul is not sent down it.
  - A parted band is NOT an enemy by construction. It carries its own view and its own
    grievances, and whether it stands with or against anyone is decided where it always
    was -- agent/allegiance.decide, on bonds, reputation and conscience. Nothing here
    writes hostility.
  - Lineages are not severed: the band keeps its memories, bonds and germ line entire.

THE GAP THIS FILLS. The substrate grows factions (§5.6, history-dependent, not label
homophily) and they take territory (§5.26, T1/T2 5/5), and the civ wheel runs schism ->
war -> collapse. But a settlement never EMITS anything: the losing bloc dies in place, and
war parties are assembled per raid from a region's members and dissolve after. So there was
no road from "factions emerge" to "bands roam the wild" -- measured by grep, no exile,
secession or departure mechanism existed anywhere.

WHY THIS SHAPE WORKS WHERE THE SCHISM WALK DID NOT. Three earlier attempts made dispersal a
CONTINUOUS FORCE on every soul, and all three failed (world/sim.py records two, and
experiment_schism the third). The diagnosis that came out of them is exactly why a discrete
event succeeds: souls cluster because they GENUINELY AGREE -- affinity discriminates on
belief at +0.606 vs -0.369 -- so pushing everyone apart fights the substrate's own honest
read. A bloc that has genuinely stopped agreeing is a different thing: it is already a
coherent group by the town's own measure, and moving it as one is going WITH that read
rather than against it.

Gated by World.parting_enabled (default off, THE RULE).
"""
from __future__ import annotations

import math

MIN_BAND = 4             # fewer than this is a loner or a pair, not a people
LEAVE_AT = -0.10         # mean alignment to the town's dominant view below which a bloc
                         # has stopped being of that town. Softer than agent.RIFT_AT
                         # (-0.3, where a single heard line WOUNDS): parting is a settled
                         # divergence, not one bad argument.
COHERENT_AT = 0.35       # a band must hold together in its OWN view, or it is not a
                         # people leaving, it is the town's unaligned tail wandering off
CHECK_EVERY = 60         # ticks between passes -- a parting is an era, not a tick
WALK = 900.0             # how far out the band's first road takes it, in world units


def _mean_align(a_souls, b_souls) -> float:
    from agent.agent import _cosine
    pairs = [(x, y) for x in a_souls for y in b_souls if x is not y]
    if not pairs:
        return 1.0
    return sum(_cosine(x.belief_vec, y.belief_vec) for x, y in pairs) / len(pairs)


def eligible(world, a) -> bool:
    """Who may take the road: a grown warrior, faring well enough to walk it. The caste,
    child and somatic floors, all three, before anything else is considered."""
    if getattr(a, "caste", "warrior") == "breeder":
        return False                                  # the hearth is kept, not turned out
    if getattr(a, "belief_vec", None) is None:
        return False
    if getattr(a, "_contraction", 0.0) > 0.5 or a.wellbeing < 0.3:
        return False                                  # the worn stay
    if world.clock_enabled:
        from world import clock as _clk
        if _clk.stage(a.age, a.lifespan) == "child":
            return False                              # children never part
    return True


def parting_tick(world) -> list:
    """One pass. Any bloc that has settled far enough from the town's dominant view --
    and holds together in its own -- takes the road as a band. Returns the bands formed
    (dicts: id, members, heading, from_view), empty on the common case of no parting."""
    if not getattr(world, "parting_enabled", False):
        return []
    if world.tick % CHECK_EVERY:
        return []
    from world.factions import factions_of

    souls = [a for a in world.agents if getattr(a, "belief_vec", None) is not None
             and not getattr(a, "band", "")]
    if len(souls) < MIN_BAND * 2:                     # a town too small to lose a people
        return []
    mapping = factions_of(world)
    blocs: dict = {}
    for a in souls:
        fid = mapping.get(a.id, -1)
        if fid >= 0:
            blocs.setdefault(fid, []).append(a)
    if len(blocs) < 2:
        return []
    dominant = max(blocs.values(), key=len)           # the town, as it sees itself

    formed = []
    for fid, bloc in blocs.items():
        if bloc is dominant or len(bloc) < MIN_BAND:
            continue
        leavers = [a for a in bloc if eligible(world, a)]
        if len(leavers) < MIN_BAND:
            continue
        if _mean_align(bloc, dominant) > LEAVE_AT:    # still of this town
            continue
        # Coherence is a property of the BLOC -- the people and its view -- not of the
        # subset fit to walk. Checking `leavers` instead was a real bug: a 14-soul bloc
        # holding together at +0.374 read as incoherent (+0.11) purely because only 4 of
        # its members were grown, healthy warriors. Who has a shared view and who can
        # take the road are different questions, and only the first defines a people.
        if _mean_align(bloc, bloc) < COHERENT_AT:
            continue                                  # not a people, just the tail
        formed.append(_take_the_road(world, leavers))
    return formed


def _take_the_road(world, leavers) -> dict:
    """The band forms: one shared heading, away from the ground it is leaving. Their
    memories, bonds and germ line come with them entire -- only their address changes."""
    bx = sum(a.position[0] for a in leavers) / len(leavers)
    by = sum(a.position[1] for a in leavers) / len(leavers)
    others = [a for a in world.agents if a not in leavers]
    if others:
        ox = sum(a.position[0] for a in others) / len(others)
        oy = sum(a.position[1] for a in others) / len(others)
        heading = math.atan2(by - oy, bx - ox)        # away from those they leave
    else:
        heading = world._rng.uniform(0.0, 2.0 * math.pi)
    band = f"band:{world.tick}.{len(getattr(world, '_bands', []))}"
    for a in leavers:
        a.band = band
        a._heading = heading
        a.memory.write("we no longer hold with them; we take our own road",
                       tick=world.tick, source="self", speaker_id=a.id,
                       emotion=-0.2, weight=1.0)
    if not hasattr(world, "_bands"):
        world._bands = []
    world._bands.append(band)
    return {"id": band, "members": [a.id for a in leavers],
            "heading": heading,
            "target": (bx + math.cos(heading) * WALK, by + math.sin(heading) * WALK)}
