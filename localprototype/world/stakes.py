"""Stakes: a contested, consequential world the affective faculties finally act ON.

Until now the souls SPOKE of trouble but nothing was lost or gained -- the grip clung to
spoken grievances, bodhicitta comforted with words. Stakes make it real: provisions under a
seasonal threat, a few CLOSED actions (work / share / hoard / tend) chosen by each soul's
ARCHETYPE (never free-form text from the model), and consequences that feed back into
wellbeing, bonds, and -- doctrinally honest -- the soul itself.

Three things make it faithful rather than a resource game:
  * REAL dukkha -- a hardship drops a soul's wellbeing and writes a CHARGED memory, so the
    existing faculties (grip amplifies, prajna loosens, transmute turns, self-lib frees, the
    ground is veiled) act on actual loss, not an abstraction.
  * CO-SUFFERING SOLIDARITY -- souls hit by the same hardship draw together (karuna from
    shared suffering), proportional to their compassion: the warm answer to scarcity.
  * KARMA, NOT EVENT -- it is the RESPONSE that conditions the soul (cetana). Meeting scarcity
    with a prosocial act plants a compassion-seed; meeting it by hoarding plants a grip +
    ill-will seed (and sours bonds). The same lean season opens one soul and hardens another,
    gradually, as seeds -- the path/vasana, not pain auto-ennobling anyone.

Opt-in: World.stakes_enabled (default off, so existing worlds and tests are unchanged).
"""

from __future__ import annotations

CONSUME = 0.04          # provisions a soul uses per tick -- more than one 'work' returns to
                        # SELF, so souls must lean on the shared commons: the safety net is
                        # load-bearing, and that is what hoarding destroys.
WORK_YIELD = 0.08       # a 'work' makes this; mostly to the commons (see the split below)
SHARE_AMT = 0.15        # provisions given in a 'share'
HOARD_AMT = 0.15        # provisions pulled from the commons in a 'hoard'
TEND_RECOVER = 0.08     # wellbeing a 'tend' restores
LOW = 0.4               # wellbeing/stores below this = scarcity / in need
HARDSHIP_LOSS = 0.9     # fraction of a victim's stores a hardship destroys (near-wipe ->
                        # the victim MUST rely on the commons to recover)
HARDSHIP_INTERVAL = 15  # ticks between seasonal hardships
COSUFFER_BOND = 0.25    # solidarity among co-sufferers (scaled by compassion)
SEED = 0.03             # how much a response under scarcity conditions the soul (karma)
SOUR = 0.05             # how much hoarding-while-others-starve sours a bond (ill-will)

HARDSHIPS = ("flood", "blight", "frost", "lean week")


def _wise_seed(a) -> None:
    # met scarcity with a prosocial response -> the heart opens a little (bhavana)
    a.compassion = min(1.0, a.compassion + SEED)


def _clinging_seed(a, others) -> None:
    # met scarcity by clinging -> the grip hardens, and ill-will toward those in need
    a.grip = min(1.0, a.grip + SEED)
    if a.bond_enabled:
        from agent.bond import Bond
        for o in others:
            if o.wellbeing < LOW:
                b = a.bonds.setdefault(o.id, Bond())
                b.trust = max(-1.0, b.trust - SOUR)


def choose_action(a, world) -> str:
    """The archetype policy: a soul's dials decide how it meets the situation -- the Grasper
    hoards under scarcity, the Lover shares with the needy, the Sage tends/accepts, all else
    works. Deterministic and legible; the LLM never picks the action."""
    others = [x for x in world.agents if x is not a]
    neediest = min(others, key=lambda x: x.wellbeing, default=None)
    commons_low = world.commons < len(world.agents) * 0.3
    scores = {"work": 0.5 + (0.6 if commons_low else 0.0)}
    # share: driven by compassion, when someone is RELATIVELY worse off than me and I can
    # spare. Relative (not an absolute floor) so the Lover keeps giving rather than depleting
    # past a gate -- the compassion gap is what makes the Lover share far more than a Grasper.
    if neediest is not None and neediest.wellbeing < a.wellbeing - 0.1 and world.commons > SHARE_AMT:
        scores["share"] = a.compassion + a.bodhicitta
    # hoard / tend: only under one's OWN scarcity -- met by the grip, or met with equanimity
    if a.wellbeing < LOW:
        scores["hoard"] = a.grip * (1.0 - a.prajna) * 1.5
        scores["tend"] = 0.4 + a.prajna + a.self_liberation
    return max(scores, key=scores.get)


def apply_action(a, action, world, now) -> None:
    others = [x for x in world.agents if x is not a]
    under_scarcity = a.wellbeing < LOW
    if action == "work":
        world.commons += WORK_YIELD * 0.8     # most of the labour goes to the shared net
        a.stores = min(1.5, a.stores + WORK_YIELD * 0.2)
        if under_scarcity:
            _wise_seed(a)
    elif action == "share":
        # the compassionate ROUTE the shared net to whoever is worst off (redistribution),
        # rather than giving from near-empty personal stores -- so sharing is actually
        # possible, and it's what lets hardship victims recover.
        neediest = min(others, key=lambda x: x.wellbeing, default=None)
        if neediest is not None:
            give = min(SHARE_AMT, max(0.0, world.commons))
            world.commons -= give
            neediest.stores += give
            neediest.memory.write(f"{a.name} saw to it I was provided for", now,
                                  source="ai", speaker_id=a.id, emotion=0.6)
            if neediest.bond_enabled:
                from agent.bond import Bond
                neediest.bonds.setdefault(a.id, Bond()).warm(0.6)
        _wise_seed(a)
    elif action == "hoard":
        take = min(HOARD_AMT, max(0.0, world.commons))
        world.commons -= take
        a.stores = min(1.5, a.stores + take)
        _clinging_seed(a, others)
    elif action == "tend":
        a.wellbeing = min(1.0, a.wellbeing + TEND_RECOVER)
        a.stores = min(1.5, a.stores + TEND_RECOVER * 0.5)
        if under_scarcity:        # equanimous self-care leaves a faint wisdom-seed
            a.prajna = min(1.0, a.prajna + SEED * 0.5)


def hardship(world, victims, now, kind="flood") -> None:
    """A seasonal blow lands on a SUBSET (not all -> it forms co-suffering sub-groups, not
    one blob). It destroys provisions, drops wellbeing (real dukkha, written as a charged
    memory the faculties meet), and binds the co-sufferers in solidarity."""
    from agent.bond import Bond
    for v in victims:
        v.stores = max(0.0, v.stores - v.stores * HARDSHIP_LOSS)
        v.wellbeing = max(0.0, v.wellbeing - HARDSHIP_LOSS * 0.5)
        # the blow is APPRAISED against what this soul's days had been (§5.15): after a good
        # stretch it lands as SHOCK (amplified, arousal), mid-slide as something braced for
        emo = -0.8
        if getattr(v, "expect_enabled", False):
            from agent import expectation
            emo = expectation.appraise_event(v, emo)
        v.memory.write(f"the {kind} took my provisions", now, source="event", emotion=emo)
    for i, v in enumerate(victims):
        for w in victims[i + 1:]:
            amt = COSUFFER_BOND * 0.5 * (v.compassion + w.compassion)
            if v.bond_enabled:
                v.bonds.setdefault(w.id, Bond()).warm(amt)
            if w.bond_enabled:
                w.bonds.setdefault(v.id, Bond()).warm(amt)
    world.bus.publish("hardship", (kind, [v.id for v in victims]))


def step(world) -> None:
    """One stakes tick: consume, fire a seasonal hardship on a localized subset on schedule,
    then let every soul act by its archetype policy."""
    rng = world._rng
    for a in world.agents:
        # consume: from your own stores first, then draw on the shared commons (the safety
        # net). wellbeing reflects BOTH being fed and having a cushion -- so living off an
        # empty commons is precarious, and going unfed (both gone) is real starvation.
        need = CONSUME
        take_self = min(a.stores, need)
        a.stores -= take_self
        short = need - take_self
        take_commons = min(max(0.0, world.commons), short)
        world.commons -= take_commons
        met = (take_self + take_commons) / need if need else 1.0
        cushion = min(1.0, a.stores * 2.0)
        a.wellbeing += 0.3 * (met * (0.5 + 0.5 * cushion) - a.wellbeing)
    if world.tick > 0 and world.tick % HARDSHIP_INTERVAL == 0 and len(world.agents) >= 2:
        k = max(1, len(world.agents) // 2)
        hardship(world, rng.sample(world.agents, k), world.tick, kind=rng.choice(HARDSHIPS))
    for a in world.agents:
        act = choose_action(a, world)
        apply_action(a, act, world, world.tick)
        a._last_action = act
