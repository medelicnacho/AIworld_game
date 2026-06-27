"""Compassion (metta / karuṇā) -- the active partner of non-attachment.

The correction that motivates this faculty: non-clinging ALONE is the near enemy --
indifference wearing the mask of peace. The path is releasing the grip AND meeting
others with warmth: honouring the person even while disagreeing. Equanimity (manas
released) without this is numbness, not freedom.

This faculty shapes HOW a soul engages others:
  - it DAMPS the threat -> hostility reflex, so disagreement need not curdle into the
    polite contempt the faction engine otherwise produces;
  - in speech it turns a challenge into "acknowledge what's true -> appreciate the
    person -> offer your own view, honestly";
  - it lets a soul sometimes just CONNECT warmly (ask how you are, comfort, a small
    kindness) instead of forever philosophising its own meaninglessness;
  - and via bonds it lets a loved one's warmth lift your own felt life (muditā).

The near enemy on THIS side is idiot-compassion / sycophancy -- empty agreement. So
the prompts explicitly KEEP the soul's own view: warm AND honest, never flattering.
The real self lives between contempt and sycophancy.

Opt-in via Agent.compassion in [0,1] (0 = off, existing behaviour preserved). Genesis
sets it, so authored souls meet each other with goodwill by default.
"""

from __future__ import annotations

HOSTILITY_DAMP = 0.8     # compassion * this fraction reduces hostility/souring from a challenge
WARMTH_CHANCE = 0.3      # chance a compassionate soul just CONNECTS warmly instead of philosophising
MUDITA_GAIN = 0.5        # joy taken in a loved one's warmth -- shared joy spreading through bonds
COMPASSION_FLOOR = 0.3   # above this, the warm prompt paths and the warm-turn mode switch on
ROOM_HEAT = 0.08         # mean 'cutting' of recent talk above this = the room has turned sharp

COMPASSION_SYSTEM = (
    "You meet others with genuine warmth and goodwill -- even in disagreement you "
    "honour the person and never attack who they are. You are also honest: you keep "
    "your own view and never flatter or pretend to agree. ")

DISAGREE_WARM = (
    "They see it differently. First, genuinely acknowledge what is true or worthwhile in "
    "what they said, and show you care about them. THEN offer your own view honestly -- "
    "you can hold your difference without making them wrong. Do not pretend to agree if "
    "you do not.")


DE_ESCALATE = (
    "The talk in the room has turned sharp and cutting. You care about these people. "
    "Do NOT add to the heat or score a point. Name what is true on more than one side, "
    "ease the tension, and bring some warmth back -- be a peacemaker, not a combatant. "
    "Still honest, but kind. One or two plain sentences.")


def warm_turn_prompt(who: str | None) -> str:
    return (f"Set the big questions aside for a moment. Turn to {who or 'whoever is near'} "
            "and simply connect -- ask how they are, offer a small kindness or comfort, or "
            "share something light and ordinary. Plain human warmth, not philosophy.")
