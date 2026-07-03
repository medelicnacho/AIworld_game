"""witness.py -- karma has EYES: what you do to one soul, in front of others, becomes
what the others expect of you.

Until now the player's (or any actor's) karma travelled two roads: direct treatment
(appraise_conduct) and broken/kept words (pledge.py). This is the third and widest road:
a WITNESSED act on a third party. Share with the starving in front of the well and every
soul in earshot warms its expectation of you a little; raid the commons while others go
hungry and every watcher cools -- and some of them will TELL it (a conduct story into the
validated C3 channel), so the deed reaches souls who never saw it: the second ring.

Two rules learned the hard way elsewhere and honoured here:
  - the story carries its charge IN ITS WORDS (the pledge falsifier's consumed-verdict
    lesson: gossip transmits feeling only through the wording -- and mind the stemmer);
  - a witnessed act moves expectation LESS than a suffered one (THIRD_RATE < the direct
    BOND_EXPECT_RATE): hearing of a knife is not feeling it.

The actor is just an id -- a soul, or the PLAYER. A game engine calls witnessed() once
per visible deed; the stakes layer calls it for share and hoard-under-scarcity."""
from __future__ import annotations

WITNESS_RADIUS = 150.0    # who counts as present (stakes towns are knots; generous)
THIRD_RATE = 0.10         # expectation moved per witnessed act (< direct treatment)
TELL_CHANCE = 0.5         # a witness that feels it may TELL it (the story that gossips)

WARM_SIG = 0.45           # how a witnessed kindness lands on expectation
DARK_SIG = -0.55          # how witnessed meanness lands


def _nudge(agent, actor_id: str, sig: float) -> None:
    exp = agent._conduct_expect.get(actor_id)
    agent._conduct_expect[actor_id] = (sig * THIRD_RATE if exp is None
                                       else exp + THIRD_RATE * (sig - exp))


def witnessed(world, actor_id: str, actor_name: str, kind: str, now: int,
              exclude=()) -> int:
    """A visible deed lands on everyone present. kind: 'kindness' | 'meanness'.
    Returns how many souls witnessed it. The actor needs no body here -- only a place:
    witnesses are souls within WITNESS_RADIUS of the actor if the actor is a soul, else
    every soul (a placeless actor -- the player at the town's heart -- is seen by all)."""
    actor = next((a for a in world.agents if a.id == actor_id), None)
    sig = WARM_SIG if kind == "kindness" else DARK_SIG
    seen = 0
    for w in world.agents:
        if w.id == actor_id or w in exclude or w.id in exclude:
            continue
        if actor is not None and world._distance(w, actor) > WITNESS_RADIUS:
            continue
        seen += 1
        _nudge(w, actor_id, sig)
        if world._rng.random() < TELL_CHANCE:
            # the telling: charged IN ITS WORDS, tagged to the actor, free to gossip
            if kind == "kindness":
                text = (f"a kindness at the well: {actor_name} saw to it the neediest "
                        f"was provided for")
                emo = 0.5
            else:
                text = (f"{actor_name} raided the commons while others went hungry -- "
                        f"a bitter, broken thing to watch")
                emo = -0.55
            w.memory.write(text, tick=now, source="event", speaker_id=actor_id,
                           emotion=emo, weight=1.1, lore_id=f"conduct:{actor_id}")
    return seen
