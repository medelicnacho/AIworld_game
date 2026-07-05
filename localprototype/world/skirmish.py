"""skirmish.py -- brawls: when the shouting is done, the angry go to each other.

The raid layer (world/war.py) is war between BLOCS -- organised, mustered, over
granaries and grudges. This is the smaller, older thing underneath it: two souls whose
quarrel has crossed into open enmity (hostility >= WAR_THRESHOLD -- accreted by the
rift's heated debates, by raid grievances, by identity threat; never assigned) stop
avoiding each other and CLOSE. A clash costs both of them; it writes charged memories
tagged to the ground it happened on; it hardens the grudge on both sides, feeding the
raid layer's muster. This is how a civilization collapses in on itself: debate becomes
enmity, enmity becomes brawls, brawls become the war.

Welfare, written before the mechanic (the standing rule):
  - CHILDREN NEVER FIGHT: the clock's stage gates both confronting and being clashed.
  - THE WORN REFUSE: a collapsed or contracted soul (the somatic floor's thresholds,
    the same numbers the muster uses) never confronts and DISENGAGES when approached
    -- it steps away; its refusal is a body's, not a coward's.
  - Deaths are RARE and CAPPED: a clash wounds; a soul falls only when the blow
    itself beats it below the edge (post-clash wellbeing < FALL_WELL) -- and since
    the worn never enter a fight, every fall is a soul that stood while still fit
    to stand, one quarrel too many. At most CASUALTY_CAP per check. The dead are
    mourned by their bonded and their lineages END (the E2 death, no bardo).
  - NO CRUELTY VERBS: a clash requires a cause (open enmity), never torment; there is
    no verb here for hurting the helpless -- the worn and the young are unreachable."""
from __future__ import annotations

SKIRMISH_CHECK = 4       # how often the world asks whether the angry have met
CLASH_RANGE = 26.0       # close enough for a quarrel to become a brawl
CONFRONT_STEP = 24.0     # an angry soul RUSHES its enemy (per check). Tuned: at 3.0
                         # the calm layer's enmity-repulsion (~2/tick) outran the
                         # confrontation and no brawl could ever happen -- anger must
                         # close faster than distaste retreats
SOLIDARITY = 0.3         # those who share the quarrel warm toward the one who stood
                         # in it -- out-group conflict cements in-group trust, which
                         # is what lets the muster (allegiance) raise a war party in
                         # an EMERGENT camp (no pre-seeded bonds anywhere)
SOLIDARITY_MIN = 1.0     # grievance toward the foe needed to feel the solidarity
CLASH_HURT = 0.12        # the wellbeing a clash costs; the loser takes ~2x
FALL_WELL = 0.15         # beaten BELOW this by the clash itself = the soul falls
CASUALTY_CAP = 1         # per check -- a brawl is a brawl, not a battle
GRUDGE_HARDEN = 0.5      # each clash deepens the enmity on both sides
KNOCKBACK = 18.0         # the brawlers are thrown apart (visible on the map)
COLLAPSED_WELL = 0.25    # the somatic floor's thresholds, shared with the muster
CONTRACTED = 0.5         # (agent/allegiance.py) -- one floor, every mechanic


def _worn(a) -> bool:
    """Too worn to stand in a quarrel -- the somatic floor, the muster's numbers."""
    return (a.wellbeing < COLLAPSED_WELL
            or getattr(a, "_contraction", 0.0) > CONTRACTED)


def _grown(world, a) -> bool:
    from world import clock as _clock
    return (not getattr(world, "clock_enabled", False)
            or _clock.stage(a.age, a.lifespan) != "child")


def _step_toward(world, a, target, dist: float, step: float) -> None:
    ax, ay = a.position
    tx, ty = target.position
    if dist <= 1e-9:
        return
    ux, uy = (tx - ax) / dist, (ty - ay) / dist
    nx, ny = ax + ux * step, ay + uy * step
    if getattr(world, "bounds", None):             # unbounded test worlds skip the clamp
        w, h = world.bounds
        nx, ny = min(max(nx, 0.0), w), min(max(ny, 0.0), h)
    a.position = (nx, ny)


def skirmish_tick(world) -> None:
    """Called by the wheel every SKIRMISH_CHECK ticks when skirmish_enabled.
    One pass: the angry CLOSE on their nearest living enemy (the worn step away
    instead), and pairs within CLASH_RANGE brawl."""
    from agent.agent import WAR_THRESHOLD
    souls = list(world.agents)
    by_id = {a.id: a for a in souls}
    fallen: list = []
    clashed: set = set()
    for a in souls:
        if a not in world.agents or a.id in clashed or not _grown(world, a):
            continue
        foes = [by_id[t] for t, h in a.hostility.items()
                if h >= WAR_THRESHOLD and t in by_id
                and _grown(world, by_id[t])]
        if not foes:
            continue
        foe = min(foes, key=lambda b: world._distance(a, b))
        d = world._distance(a, foe)
        if _worn(a):
            # the somatic floor: too worn for a quarrel -- disengage, step away
            _step_toward(world, a, foe, d, -CONFRONT_STEP)
            continue
        if d > CLASH_RANGE:
            _step_toward(world, a, foe, d, CONFRONT_STEP)  # the angry go to each other
            continue
        if _worn(foe) or foe.id in clashed:
            continue                       # the worn are unreachable; one brawl each
        # THE CLASH: both are hurt, the weaker roughly twice as hard
        rng = world._rng
        a_str = getattr(a, "boldness", 0.5) * max(0.1, a.wellbeing) * rng.uniform(0.8, 1.2)
        f_str = getattr(foe, "boldness", 0.5) * max(0.1, foe.wellbeing) * rng.uniform(0.8, 1.2)
        winner, loser = (a, foe) if a_str >= f_str else (foe, a)
        winner.wellbeing = max(0.0, winner.wellbeing - CLASH_HURT)
        loser.wellbeing = max(0.0, loser.wellbeing - 2.0 * CLASH_HURT)
        clashed.add(a.id)
        clashed.add(foe.id)
        # thrown apart -- the brawl is visible on the map
        _step_toward(world, winner, loser, max(1e-6, world._distance(winner, loser)),
                     -KNOCKBACK / 2)
        _step_toward(world, loser, winner, max(1e-6, world._distance(loser, winner)),
                     -KNOCKBACK)
        # the quarrel deepens on BOTH sides -- brawls feed the raid layer's grudge
        a.hostility[foe.id] = a.hostility.get(foe.id, 0.0) + GRUDGE_HARDEN
        foe.hostility[a.id] = foe.hostility.get(a.id, 0.0) + GRUDGE_HARDEN
        ground = ""
        if getattr(world, "regions_enabled", False) and world.regions is not None:
            ground = world.regions.name_of(a.position)
        where = f" by {ground}" if ground else ""
        tag = f"brawl:{world.regions.index(a.position)}" if ground else "brawl:town"
        loser.memory.write(f"{winner.name} and I came to blows{where}, and I was "
                           f"beaten -- the quarrel is past words now",
                           tick=world.tick, source="event", speaker_id=winner.id,
                           emotion=-0.5, weight=1.1, lore_id=tag)
        winner.memory.write(f"{loser.name} and I came to blows{where}; I stood, "
                            f"but nothing is settled",
                            tick=world.tick, source="event", speaker_id=loser.id,
                            emotion=-0.35, weight=1.1, lore_id=tag)
        # SOLIDARITY: everyone in earshot who shares the quarrel warms toward the
        # one who stood in it. This is how an emergent camp grows the TRUST the
        # muster reads -- war parties are recruited by the brawls that precede war.
        from agent.bond import Bond
        reach = getattr(world, "hearing_range", 50.0)
        for fighter, other in ((winner, loser), (loser, winner)):
            for c in souls:
                if (c is fighter or c is other or c not in world.agents
                        or not _grown(world, c)
                        or c.hostility.get(other.id, 0.0) < SOLIDARITY_MIN
                        or world._distance(c, fighter) > reach):
                    continue
                c.bonds.setdefault(fighter.id, Bond()).warm(SOLIDARITY)
        world.bus.publish("skirmish", {"tick": world.tick, "a": winner.name,
                                       "b": loser.name, "ground": ground})
        # a soul falls only when the blow itself beat it below the edge -- and
        # at most CAP per check (the worn never entered, so every fall is a soul
        # that stood while still fit to stand)
        if len(fallen) < CASUALTY_CAP:
            if loser.wellbeing < FALL_WELL:
                fallen.append(loser)
            elif winner.wellbeing < FALL_WELL:
                fallen.append(winner)
    for dead in fallen:
        world._mourn(dead)                 # the loss lands on those who loved them
        world.agents = [x for x in world.agents if x is not dead]
        world.bus.publish("skirmish_death", dead.id)
        world.bus.publish("death", dead.id)
