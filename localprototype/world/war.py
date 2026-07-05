"""war.py -- raids over lean granaries: war as karma at faction scale.

Nothing here invents aggression. A raid happens when the machinery that already exists
says it must: a bloc whose HOME GROUND (factions.home_region -- the territory V2 proved
they take) can no longer feed them looks at a fatter granary, its members DECIDE
individually through the measured muster (boldness, trust, conscience -- and the worn
refuse: the somatic floor extends to war, verdict 5/5), and the willing go. The fight
is bodies, not dice alone; the dead are mourned and their lineages END (no bardo -- an
ecology's death is the E2 kind); the loot moves real food between real pools; and every
defender writes a GRIEVANCE whose charge lives in its words (the pledge lesson) and
whose lore-tag is keyed to the LAND (feud:crag>vale), so a feud can outlive every soul
who started it -- carried the way legends are carried.

Welfare, written before the mechanic (the standing rule): the somatic floor stays on;
casualties are capped per raid; the dead get the same mourning any death gets; there
are no cruelty verbs here -- conflict is over food and grievance, never torment."""
from __future__ import annotations

RAID_CHECK = 40          # how often the world asks "is anyone hungry enough"
HUNGER_LINE = 0.35       # home pool per member below this = the granary can't feed them
FAT_LINE = 2.0           # a target must actually be worth marching for
MIN_PARTY = 2            # nobody raids alone
DANGER = 0.7             # what the muster is asked to face
LOOT_FRAC = 0.35         # share of the defenders' pool taken on a won raid
CASUALTY_CAP = 2         # per side, per raid -- a raid is a raid, not an apocalypse
GRIEF_EMO, GRIEF_W = -0.8, 1.4


def _power(crew, rng) -> float:
    return sum(getattr(a, "boldness", 0.5) * max(0.1, a.wellbeing) for a in crew) \
        * rng.uniform(0.8, 1.2)


def _fall(crew, rng, cap: int) -> list:
    """Who falls: up to cap, the frail more likely (weighted by 1 - wellbeing)."""
    fallen = []
    pool = list(crew)
    for _ in range(min(cap, max(0, len(pool) - 1))):   # a side is never wiped out
        weights = [max(0.05, 1.0 - a.wellbeing) for a in pool]
        total = sum(weights)
        r = rng.uniform(0, total)
        for a, wt in zip(pool, weights):
            r -= wt
            if r <= 0:
                fallen.append(a)
                pool.remove(a)
                break
    return fallen


def war_tick(world) -> None:
    """Called by the wheel every RAID_CHECK ticks when war_enabled. One raid at most
    per check -- wars are punctuation, not weather."""
    from agent import allegiance
    from world import factions as F
    if not getattr(world, "regions_enabled", False) or world.regions is None:
        return
    mapping = F.factions_of(world)
    blocs = sorted({f for f in mapping.values() if f != F.LONER})
    homes = {f: F.home_region(world, f, mapping) for f in blocs}
    rng = world._rng
    for atk in blocs:
        crew = F.members(world, atk, mapping)
        home = homes[atk]
        if home is None or len(crew) < 3:
            continue
        hunger = world.regions.pools[home] / max(1, len(crew))
        # grievance lowers the threshold: a bloc that HATES a neighbour will march on a
        # fuller belly than mere hunger would move it. Feuds feed the next war -- so a
        # war of desperation, once fought, can become a war of grudge that outlives it.
        def grudge_against(other_ids):
            return sum(a.hostility.get(o, 0.0) for a in crew for o in other_ids) \
                / max(1, len(crew))
        cand = [f for f in blocs
                if f != atk and homes[f] is not None and homes[f] != home
                and world.regions.pools[homes[f]] >= FAT_LINE]
        if not cand:
            continue
        fmembers = {f: {b.id for b in F.members(world, f, mapping)} for f in cand}
        grudge = {f: grudge_against(fmembers[f]) for f in cand}
        threshold = HUNGER_LINE + max(grudge.values()) * 0.5   # hate raises the line hunger must clear
        if hunger >= threshold:
            continue
        # target the fattest granary, but a real grudge overrides mere fatness
        dfd = max(cand, key=lambda f: (grudge[f] * 3.0
                                       + world.regions.pools[homes[f]] / 6.0))
        atk_lead = F.leader_of(world, atk, mapping)
        dfd_lead = F.leader_of(world, dfd, mapping)
        if atk_lead is None or dfd_lead is None:
            continue
        # THE MUSTER DECIDES -- individually, for both sides (the measured organ:
        # boldness, trust, conscience; the worn refuse regardless of loyalty)
        from world import clock as _clock
        grown = lambda a: (not getattr(world, "clock_enabled", False)
                           or _clock.stage(a.age, a.lifespan) != "child")
        party = [a for a in crew if grown(a) and (a is atk_lead
                 or allegiance.decide(a, atk_lead.id, danger=DANGER)[0] == "join")]
        if len(party) < MIN_PARTY:
            continue
        defenders = [a for a in F.members(world, dfd, mapping) if grown(a) and
                     (a is dfd_lead
                      or allegiance.decide(a, dfd_lead.id, danger=DANGER)[0] == "join")]
        # ALLIES: a third bloc whose view stands with the defenders and against the
        # attackers sends ITS willing too -- join forces, emergently
        from agent.agent import _cosine
        for ally in blocs:
            if ally in (atk, dfd):
                continue
            al = F.leader_of(world, ally, mapping)
            if al is None or al.belief_vec is None or dfd_lead.belief_vec is None:
                continue
            if (_cosine(al.belief_vec, dfd_lead.belief_vec) >= 0.45
                    and atk_lead.belief_vec is not None
                    and _cosine(al.belief_vec, atk_lead.belief_vec) < 0.0):
                defenders += [a for a in F.members(world, ally, mapping)
                              if allegiance.decide(a, al.id, danger=DANGER)[0] == "join"]
        won = _power(party, rng) > _power(defenders, rng) if defenders else True
        losers = defenders if won else party
        fallen = _fall(losers, rng, CASUALTY_CAP)
        loot = 0.0
        if won:
            take = world.regions.pools[homes[dfd]] * LOOT_FRAC
            world.regions.pools[homes[dfd]] -= take
            world.regions.pools[home] += take
            loot = take
        atk_banner = F.banner_of(world, atk, mapping)
        dfd_banner = F.banner_of(world, dfd, mapping)
        feud = f"feud:{home}>{homes[dfd]}"
        fallen_names = ", ".join(a.name for a in fallen) or "no one"
        # GRIEVANCE lands on every defender-bloc soul: charge IN THE WORDS, tagged to
        # the LAND so the feud can outlive everyone who started it
        for a in F.members(world, dfd, mapping):
            a.memory.write(
                f"{atk_banner} came for our granary -- {fallen_names} fell, and the "
                f"bread of {dfd_banner.split('of ')[-1]} was carried off; a bitter, "
                f"broken day", tick=world.tick, source="event",
                emotion=GRIEF_EMO, weight=GRIEF_W, lore_id=feud)
            # NOTE (handoff): grievances still DECAY -- memory.py has no salience_floor
            # field, so a feud fades unless retold. Making feuds persist to a late tick
            # is the OPEN G2 problem (see ECOLOGY_PLAN.md).
            for m in party:
                a.hostility[m.id] = a.hostility.get(m.id, 0.0) + 1.0
        for a in party:
            a.memory.write(
                f"we marched on {dfd_banner.split('of ')[-1]} because our children "
                f"were thin; {fallen_names} did not come home", tick=world.tick,
                source="event", emotion=-0.25, weight=1.1, lore_id=feud)
        # the dead are MOURNED and their lineages END -- the ecology's death is real
        for a in fallen:
            world._mourn(a)
            world.agents = [x for x in world.agents if x is not a]
            world.bus.publish("war_death", a.id)
            world.bus.publish("death", a.id)
        world._war_log.append({"tick": world.tick, "atk": home, "dfd": homes[dfd],
                               "won": won, "fallen": [a.name for a in fallen],
                               "party": [a.id for a in party],
                               "defenders": [a.id for a in defenders], "loot": loot})
        del world._war_log[:-200]
        world.bus.publish("raid", {"tick": world.tick, "atk": atk_banner,
                                   "dfd": dfd_banner, "won": won,
                                   "fallen": [a.name for a in fallen]})
        return                                          # one raid per check, at most
