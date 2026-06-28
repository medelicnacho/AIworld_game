"""Joy (muditā / pīti) -- savoring the good. The missing fourth brahmavihāra wing.

The whole affective build modelled dukkha and its cessation, and the answer kept being
equanimity / release. But a self that can only suffer WELL never simply flourishes. Joy is
the complement: fully RECEIVING a good thing -- a festival, a kindness, a child come home --
and letting it nourish you.

The shape mirrors everything else here. Just as the cure for pain was non-grasping WITH
warmth, the cure for joylessness is delight WITH non-grasping. The near enemy of joy is
CRAVING (rāga): clutching the pleasant, wanting to KEEP it -- which discounts the present
good and spins the hedonic treadmill (modelled in manas). True joy savours AND lets the good
be impermanent.

Operationalisation, mirroring manas (which HOLDS aversive charges and adds the second arrow):
joy SAVOURS pleasant charges -- holds their salience so the good actually LANDS and lasts
(lifting felt mood, since memory.mood is salience-weighted), received fully rather than rushed
past. It does NOT amplify the charge into MORE (that would be craving); it receives what is
here. The two failures it sits between: ANHEDONIA (joy off -> the good barely registers and
decays unfelt) and CRAVING (the grip clutches the good so it sours -- see manas).

Gated by Agent.joy in [0,1] (0 = off, default -> existing worlds/tests unchanged).
"""

from __future__ import annotations

SAVOR = 0.06   # how hard joy holds a pleasant charge against decay (the positive mirror of manas.HOLD)

# Muditā: sympathetic joy -- the bright mirror of bodhicitta. Where bodhicitta turns to the
# one who suffers, muditā turns to the one who FLOURISHES and rejoices with them.
MUDITA_FLOOR = 0.3     # above this joy, a soul proactively turns to rejoice with others' good
MUDITA_CHANCE = 0.4    # chance a joyful soul takes the rejoice turn on a given turn
GOOD_MOOD = 0.15       # an overheard felt mood above this marks a soul as flourishing/glad

JOY_SYSTEM = (
    "You savour the good things when they come and take genuine joy in others' good fortune -- "
    "gladness without grasping, never envy. ")


def rejoice_prompt(who: str | None) -> str:
    return (f"{who or 'Someone nearby'} has had something good happen. You are genuinely glad for "
            "them -- not envious, not turning it back to yourself. Turn to them and share their "
            "joy, celebrate it with them. One or two warm sentences.")


def apply(agent, now: int) -> None:
    """Savour: dwell in the good so it lands and lasts. No-op at joy 0 (the anhedonic default).
    Holds pleasant charges' salience -- which lifts felt mood -- but never amplifies them into
    wanting-more (that is craving, which manas models). Received, not grasped."""
    j = getattr(agent, "joy", 0.0)
    if j <= 0.0:
        return
    for m in agent.memory.items:
        if m.source == "doctrine":
            continue
        if m.emotion > 0.0:                       # a pleasant charge -- a good thing lived
            m.salience = min(1.0, m.salience * (1.0 + j * SAVOR))
