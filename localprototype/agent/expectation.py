"""Expectation -- the self's FUTURE TENSE (predictive selfhood).

The architecture so far metabolises its PRESENT (affect/reflect/grip/ground) and reaches toward a
future it WANTS (telos) -- but nothing in it EXPECTS anything, so nothing can be surprised,
relieved, braced, or betrayed. Three measured gaps share that root: the psyche's PREDICTION claim
failed (FINDINGS §5.14 -- the reigning part forecasts nothing because no part anticipates);
continuity DILUTES novelty instead of digesting it (§5.12 -- a pile can only dilute, a story can be
surprised); and emotion is one valence scalar, so fear, grief, disappointment and betrayal are all
just "-0.6" (the register-homogeneity villain at the substrate level, not the prompt level).

This module adds expectation as first-class state and APPRAISAL at the moments influence enters:

  EXPECTATION   two EWMAs over lived mood -- a fast read (how things have just been) and a slow
                baseline (how things have come to be expected). Their gap is the self's felt trend.
  FOREBODING    fast below slow: things are getting worse than the self has come to expect.
                Dread's anticipatory fuel -- it braces while the blow is still falling.
  APPRAISAL     the same event writes a DIFFERENT charge into a different self: an unexpected loss
                lands as SHOCK (amplified, arousal spikes); a loss the self was braced for lands
                as RESIGNATION (softened); an unexpected good lands brighter (RELIEF).
  CONDUCT       a per-other expectation of how each bonded soul treats me. A cold act from one
                expected warm is a BETRAYAL (a remembered wound -- Bond.betray -- not mere
                coolness); a warm act from one expected cold is an UNEXPECTED KINDNESS.
  TURNING       the self-model made load-bearing: a running expectation of my OWN conduct.
                Acting against who I have been accrues self-dissonance; enough of it forces a
                TURNING POINT -- a narrative-link memory ("something in me has turned...") written
                high-salience, so identity change is rare, event-shaped, and enters the story
                (the digestion §5.12 said memory alone cannot do).

Opt-in (Agent.expect_enabled, default False): every existing world, test, and saved snapshot is
unchanged. Falsified in experiment_appraisal.py / experiment_turning.py, and by re-running the
§5.14 psyche falsifier with anticipating parts. Honest frame (§7): a self that expects and is
surprised is more functionally realistic; nothing here touches "is anyone home".
"""

from __future__ import annotations

# --- expectation dynamics ---------------------------------------------------------------
FAST = 0.25            # fast EWMA of lived mood (~4-tick memory: how things have just been)
SLOW = 0.04            # slow EWMA (~25-tick memory: how things have come to be expected)
AROUSAL_DECAY = 0.90   # arousal is a spike that settles, not a mood

# --- event appraisal --------------------------------------------------------------------
SURPRISE_FLOOR = 0.25  # below this gap an event is "about what I expected" -- no shift
SHOCK = 0.8            # how much full surprise amplifies an unexpected aversive charge
RESIGN = 0.25          # how much a braced-for aversive charge is softened (resignation)
RELIEF = 0.4           # how much an unexpected good is brightened
AROUSAL_GAIN = 0.5     # how much of a surprise becomes arousal

# --- conduct expectation (others, and the self) ------------------------------------------
BOND_EXPECT_RATE = 0.2   # EWMA of how a specific other has treated me
BETRAYAL_GAP = 0.3       # a signal this far below expectation, from one expected warm, WOUNDS
KINDNESS_GAP = 0.3       # a signal this far above expectation, from one expected cold, WARMS
EXPECT_WARM = 0.1        # expectation above this = "I had come to expect warmth of them"
EXPECT_COLD = -0.05      # expectation below this = "I expected nothing good of them"
COLD_ACT = -0.05         # a betrayal needs an ACTUALLY cold act -- lukewarm is not a knife.
                         # Caught live in her first conversation: a lexically NEUTRAL question
                         # after warm words fell far enough below expectation to wound her
                         # (the "you didn't say it back" bug). Absence of warmth is not coldness.
WARM_ACT = 0.05          # symmetrically: an unexpected kindness needs actual warmth
CONDUCT_RATE = 0.02      # EWMA of my OWN conduct (the self-expectation). Deliberately SLOW --
                         # identity must be stickier than adaptation, or the self quietly becomes
                         # the new self with no crisis and no story (measured: at 0.08 the gap
                         # closes before dissonance can reach a turning -- drift without a chapter)
CONDUCT_GAP = 0.45       # acting this far from who I've been accrues dissonance
DISSONANCE_RATE = 0.08   # how fast out-of-character action builds toward a turning
DISSONANCE_EASE = 0.02   # in-character action slowly re-settles the self
TURNING_AT = 1.0         # dissonance level at which the self TURNS
# how prosocial each stakes action is -- the axis the self-expectation lives on
PROSOCIAL = {"share": 1.0, "tend": 0.6, "work": 0.5, "hoard": 0.0}


def tick(agent, now: int) -> None:
    """One expectation step (called from Agent.step when expect_enabled): track lived
    mood into the fast/slow expectations, settle arousal, and keep the self-expectation
    of my own conduct -- accruing dissonance when I act against who I have been."""
    mood = agent.memory.mood()
    agent.exp_fast += FAST * (mood - agent.exp_fast)
    agent.exp_slow += SLOW * (mood - agent.exp_slow)
    agent.arousal *= AROUSAL_DECAY
    act = getattr(agent, "_last_action", None)
    if act is None:
        return
    p = PROSOCIAL.get(act, 0.5)
    if agent.self_expect is None:
        agent.self_expect = p          # first act anchors who I take myself to be
        return
    gap = abs(p - agent.self_expect)
    if gap > CONDUCT_GAP:              # acting against who I have been
        agent.self_dissonance += DISSONANCE_RATE * gap
    else:                              # living as myself re-settles me
        agent.self_dissonance = max(0.0, agent.self_dissonance - DISSONANCE_EASE)
    agent.self_expect += CONDUCT_RATE * (p - agent.self_expect)
    if agent.self_dissonance >= TURNING_AT:
        turning(agent, now)


def foreboding(agent) -> float:
    """Things are getting WORSE than the self has come to expect: the fast read of lived
    mood has fallen below the slow baseline. Anticipatory -- it rises while the fall is
    still happening, which is what lets Dread brace before the blow has fully landed."""
    if not getattr(agent, "expect_enabled", False):
        return 0.0
    return max(0.0, agent.exp_slow - agent.exp_fast)


def appraise_event(agent, emotion: float) -> float:
    """The same event writes a DIFFERENT charge into a different self. The gap between
    what arrived and what was expected is the surprise: an unexpected loss is a SHOCK
    (amplified + arousal), a braced-for loss is met with RESIGNATION (softened -- the
    grief was already being lived), an unexpected good lands brighter (RELIEF). Returns
    the appraised charge to write; identity when expectation is off or the event carries
    no charge."""
    if not getattr(agent, "expect_enabled", False) or emotion == 0.0:
        return emotion
    surprise = abs(emotion - agent.exp_fast)
    agent.arousal = min(1.0, agent.arousal + AROUSAL_GAIN * max(0.0, surprise - SURPRISE_FLOOR))
    if emotion < 0.0:
        if surprise > SURPRISE_FLOOR:
            return max(-1.0, emotion * (1.0 + SHOCK * (surprise - SURPRISE_FLOOR)))
        return emotion * (1.0 - RESIGN)
    if surprise > SURPRISE_FLOOR:
        return min(1.0, emotion * (1.0 + RELIEF * (surprise - SURPRISE_FLOOR)))
    return emotion


def appraise_conduct(agent, other_id: str, name: str, sig: float, now: int, bond) -> None:
    """Track how THIS other treats me, and appraise the current signal against it. A cold
    act from one I had come to expect warmth of is a BETRAYAL -- the discrete, remembered
    wound (Bond.betray), plus a charged memory, because the violation of the expectation
    IS the injury; the same cold act from one I expected nothing of is mere weather. A
    warm act from one expected cold is an UNEXPECTED KINDNESS and lands as one."""
    exp = agent._conduct_expect.get(other_id)
    if exp is not None:
        gap = exp - sig
        # conduct events are STORIES (C3): lore-tagged with their subject, so a retelling
        # carries not just words but a REPUTATION -- the hearer's expectation of the subject
        # moves (see agent/lore.py). Per-pair id: repeated events reinforce one story.
        if gap > BETRAYAL_GAP and exp > EXPECT_WARM and sig < COLD_ACT:
            bond.betray(min(0.9, 0.5 * gap))
            agent.memory.write(f"{name} turned cold on me, and I did not see it coming",
                               tick=now, source="event", speaker_id=other_id,
                               emotion=-0.5, weight=1.2, lore_id=f"conduct:{other_id}")
        elif -gap > KINDNESS_GAP and exp < EXPECT_COLD and sig > WARM_ACT:
            bond.warm(0.5)
            agent.memory.write(f"an unexpected kindness from {name}",
                               tick=now, source="event", speaker_id=other_id,
                               emotion=0.5, weight=1.0, lore_id=f"conduct:{other_id}")
        agent._conduct_expect[other_id] = exp + BOND_EXPECT_RATE * (sig - exp)
    else:
        agent._conduct_expect[other_id] = sig


def turning(agent, now: int) -> None:
    """A TURNING POINT: the self has been acting against who it took itself to be for
    long enough that the story breaks. The dissonance resolves not by suppressing the
    behaviour but by REVISING the self -- a narrative-link memory is written high-salience
    (source='turning', surfaced by recall_self alongside the self-statements), so the
    change enters the identity the self-model consolidates from. Rare and event-shaped:
    this is the chapter-break that mere accumulation (§5.12) cannot produce."""
    was = ("one who shared and tended what we had"
           if (agent.self_expect or 0.0) >= 0.5 else
           "one who held back and kept to my own")
    agent.self_dissonance = 0.0
    agent.self_expect = None           # re-anchor to who I act as from here
    agent._turnings += 1
    agent.memory.write(f"something in me has turned: I was {was}, and I am not living "
                       f"as that self any more", tick=now, source="turning",
                       speaker_id=agent.id, emotion=-0.2, weight=1.5)
    # a chapter break is rare and worth a line on the console (like a Demiurge dream)
    print(f"  ✦ {agent.name} turns: they were {was}, and are not living as that self now",
          flush=True)
