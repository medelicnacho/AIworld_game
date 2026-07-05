"""Lore -- gossip that mutates into legend (transmission with per-holder drift).

The memory substrate already does the two halves separately: memories BLUR as they age
(MemoryStore._mutate -- one word lost, vaguer, reordered per mutation) and speech seeds
listeners' memories. This module chains them: souls RETELL their most salient story --
their memory's CURRENT, already-drifted text -- and listeners write that version, which
then drifts further in them. Over generations (the wheel), the witnesses die and only
retellings of retellings remain: a real event survives as a LEGEND whose text has
mutated but whose provenance (Memory.lore_id, carried through every retelling) is
ground truth back to what actually happened.

Two existing dynamics do the interesting work, neither added here:
  REHEARSAL STABILIZES  a retold story is touched (reinforced) -- and _mutate only fires
                        on memories untouched for MUTATE_MIN_AGE ticks -- so the versions
                        a community keeps telling drift SLOWLY while neglected copies rot.
  MERGE CANONIZES       write() folds a similar incoming retelling into the resident copy
                        (salience up, text kept), so popular variants accumulate salience,
                        get retold more, and a dominant version can emerge.

Deliberately NOT routed through hear() (like the murmur): a retelling touches memory
only -- no affinity, ideology, or grace machinery. The story's own valence still lands
(memory.write derives it), so a dark legend darkens its hearers a little. That is what
stories do.

Opt-in: World.lore_enabled (default off). Falsified in experiment_lore.py: does the
event outlive its witnesses (vs the murmur-only null)? does it mutate yet stay traceable?
does the community converge on a canonical variant? is the drift path-dependent?
"""

from __future__ import annotations

RETELL_INTERVAL = (25, 60)   # ticks between one soul's retellings (staggered, like murmur)
RETELL_RANGE = 180.0         # how far a told story carries (a fireside, not a proclamation)
RETELL_FANOUT = 2            # a telling reaches a FEW hearers, not the whole square -- load-bearing:
                             # rehearsal (being re-heard) shields a copy from mutation, so a broadcast
                             # would freeze the legend into a verbatim record; sparse gossip leaves the
                             # quiet stretches in which each holder's copy drifts
RETELL_WEIGHT = 0.5          # lands harder than an overheard mutter (0.3), softer than speech
RETELL_REINFORCE = 0.15      # telling re-engraves the teller's own copy (rehearsal)
REP_RATE = 0.15              # reputation (C3): how far a heard CONDUCT story moves the hearer's
                             # expectation of its subject -- weaker than direct experience (0.2),
                             # because gossip is testimony, not a scar of one's own


def pick(agent):
    """The story this soul would tell: its most salient lore-tagged memory (a retelling
    it holds, or an event it witnessed). None if it carries no stories."""
    stories = [m for m in agent.memory.items if getattr(m, "lore_id", "")]
    return max(stories, key=lambda m: m.salience) if stories else None


def retell(world) -> None:
    """One lore pass over the world: souls whose turn has come tell their story to
    whoever is near. The teller's copy is reinforced (rehearsal -- which also shields
    it from mutation for a while); each listener writes the teller's CURRENT text,
    provenance carried. Called from World.step/advance when lore_enabled."""
    for a in world.agents:
        cd = getattr(a, "_retell_cd", None)
        if cd is None:
            cd = world._rng.randint(*RETELL_INTERVAL)
        cd -= 1
        if cd > 0:
            a._retell_cd = cd
            continue
        a._retell_cd = world._rng.randint(*RETELL_INTERVAL)
        story = pick(a)
        if story is None:
            continue
        story.salience = min(1.0, story.salience + RETELL_REINFORCE)
        story.last_touched_tick = world.tick
        near = [b for b in world.agents
                if b is not a and world._distance(a, b) <= RETELL_RANGE]
        for b in world._rng.sample(near, min(RETELL_FANOUT, len(near))):
            # the salience floor travels WITH the telling (like lore_id): a grievance
            # retold is a grievance kept -- this is how a feud reaches souls not yet
            # born when it was cut and does not fade in them (G2). Ordinary stories
            # carry floor 0 and forget as they always did.
            b.memory.write(story.text, tick=world.tick, source="lore",
                           speaker_id=a.id, weight=RETELL_WEIGHT,
                           lore_id=story.lore_id,
                           salience_floor=getattr(story, "salience_floor", 0.0))
            # REPUTATION (C3): a conduct story moves the hearer's expectation of its SUBJECT --
            # reputation as transmitted expectation, riding the same mutating channel as any
            # legend (so reputations travel, distort, and can be unfair). Third parties only:
            # the subject hearing gossip about itself is not evidence of how it treats people.
            if story.lore_id.startswith("conduct:") and getattr(b, "expect_enabled", False):
                subject = story.lore_id.split(":", 1)[1]
                if subject and subject != b.id:
                    exp = b._conduct_expect.get(subject, 0.0)
                    b._conduct_expect[subject] = exp + REP_RATE * (story.emotion - exp)
        world.bus.publish("lore", (a.id, story.lore_id, story.text))
