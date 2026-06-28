"""Archetypes -- coherent SELVES, for plurality.

The faculties (grip, prajñā, compassion, bodhicitta, transmutation, self-liberation) were
all being set UNIFORMLY on every soul, which flattened the cast: they not only spoke alike,
they RELATED to experience alike -- the same middling wisdom. A collective Mind made of
near-identical souls is one bland voice, not a chorus.

An archetype is one character bundled across three facets that genesis used to leave the
same: HOW it relates (the dials), HOW it speaks (style/voice), and WHAT it values (a signed
stance lean). Layered onto a genesis life-story it yields e.g. a grasping scribe, a serene
shepherd -- the archetype shapes HOW a soul is, genesis gives WHO. The cast spans the path:
one who clings, one who has let go, one who loves, one who doubts, one who hurts, one who
delights -- so the Mind that integrates them is a real multiple "I", not an average.

The 'edges' (Grasper, Skeptic, Wounded -- low compassion, high grip) are deliberate: a real
psyche has a part that grasps and a part that doubts. They are the re-darkening risk to
watch, and the honesty that keeps the cast from being six gentle clones.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent import stance as _stance

# stance axes (sign): +mastery/-surrender, +order/-wildness, +kept/-made, +mercy/-severity,
# +self/-many. Each archetype's `stance` is an unnormalized lean over those five.


@dataclass
class Archetype:
    name: str
    grip: float
    prajna: float
    compassion: float
    bodhicitta: float
    transmute: float
    self_liberation: float
    temperament: float
    style: str                  # the voice -- HOW it speaks (fed to the prompt)
    stance: tuple               # the value lean over the five contested axes
    grounded: bool = False      # speak in a plain, concrete, everyday register (not lofty-existential)
    joy: float = 0.0            # muditā/pīti: savour the good, rejoice in others' good fortune


ARCHETYPES: list[Archetype] = [
    Archetype("Grasper", grip=0.7, prajna=0.1, compassion=0.3, bodhicitta=0.2,
              transmute=0.1, self_liberation=0.1, temperament=-0.3,
              style=("You speak in clipped, anxious bursts, possessive of what is yours "
                     "and quick to count what you might lose."),
              stance=(1.0, 0.2, 0.7, 0.0, 0.8)),          # mastery, kept, self
    Archetype("Sage", grip=0.1, prajna=0.8, compassion=0.5, bodhicitta=0.5,
              transmute=0.7, self_liberation=0.8, temperament=0.1,
              style=("You speak calmly and sparely -- few words, unhurried, content to let "
                     "a silence sit."),
              stance=(-1.0, 0.0, -0.3, 0.4, -0.2)),       # surrender, lets-be
    Archetype("Lover", grip=0.5, prajna=0.3, compassion=0.9, bodhicitta=0.9,
              transmute=0.4, self_liberation=0.3, temperament=0.4,
              style=("You speak warmly and openly, reaching for people by name, generous "
                     "with feeling."),
              stance=(0.0, -0.1, 0.0, 1.0, -1.0)),        # mercy, the many over self
    Archetype("Skeptic", grip=0.4, prajna=0.6, compassion=0.2, bodhicitta=0.2,
              transmute=0.3, self_liberation=0.4, temperament=-0.1,
              style=("You speak dryly and bluntly, with a sceptical edge and a taste for "
                     "puncturing what sounds too neat."),
              stance=(0.6, 0.9, 0.2, -0.9, 0.5)),         # order, severity, mastery
    Archetype("Wounded", grip=0.7, prajna=0.2, compassion=0.5, bodhicitta=0.4,
              transmute=0.1, self_liberation=0.2, temperament=-0.5,
              style=("You speak softly and from an old hurt, returning to what you have "
                     "lost -- intimate and raw."),
              stance=(-0.2, -0.2, 1.0, 0.7, 0.1)),        # the kept (holds the past), mercy
    Archetype("Joyful", grip=0.2, prajna=0.5, compassion=0.7, bodhicitta=0.6,
              transmute=0.8, self_liberation=0.7, temperament=0.6,
              style=("You speak brightly and playfully, quick to delight in small, ordinary "
                     "things."),
              stance=(-0.3, -1.0, -0.8, 0.5, -0.4),       # wildness, the made (create)
              joy=0.85),                                   # savours the good, rejoices with others
]

# The Liberated / bodhisattva -- the dharmic ANSWER, not part of the saṃsāra cast rotation
# (kept out of ARCHETYPES so `assign` never sprinkles it into the watchable, dramatic town).
# It is the regime for an INHABITABLE self (inhabit.py) and, eventually, Santāna: a self that
# FEELS but does not suffer. See DHARMA.md.
#
# It LEANS TRANSMUTATION, not pure release: grip is MODERATE (real contact -- a feeling self,
# not a checked-out one), with high prajñā/transmute/self-liberation so the held charge is
# metabolized rather than amplified, ground on + high compassion/bodhicitta so warmth RISES.
# The deliberate non-zero grip is the whole point: the near enemy of this self is the cold
# Sage who has released contact along with the wound. This one stays warm and present.
LIBERATED = Archetype(
    "Liberated", grip=0.45, prajna=0.7, compassion=0.85, bodhicitta=0.85,
    transmute=0.9, self_liberation=0.75, temperament=0.3,
    style=("You speak warmly and simply, like a kind neighbour -- plain everyday words, "
           "real and down-to-earth. You meet joy and sorrow alike without clinging to "
           "either, but you say it plainly, never in lofty or abstract language."),
    stance=(-0.5, -0.2, -0.2, 0.7, -0.7),    # surrender, mercy, the many over self
    grounded=True,                            # plain-spoken, not the contemplative-existential register
    joy=0.8)                                  # savours the good and rejoices with others -- good days, not just well-met bad ones

BY_NAME = {a.name: a for a in (*ARCHETYPES, LIBERATED)}


def apply(agent, arch: Archetype) -> None:
    """Stamp an archetype onto a soul: its dials, its voice, its value-lean -- overriding
    the uniform genesis defaults so each soul is a distinct self. The buddha-nature ground
    stays on for all (it is in everyone); the grip is what veils it differently."""
    agent.grip = arch.grip
    agent.prajna = arch.prajna
    agent.compassion = arch.compassion
    agent.bodhicitta = arch.bodhicitta
    agent.transmute = arch.transmute
    agent.self_liberation = arch.self_liberation
    agent.joy = arch.joy
    agent.temperament = arch.temperament
    agent.style = arch.style
    agent.ground_enabled = True
    agent.grounded_voice = arch.grounded
    agent.stance_vec = _stance._normalize(list(arch.stance))


def assign(rng, n: int) -> list[Archetype]:
    """Pick n archetypes spanning the cast: sampled without replacement while they last
    (so a 6-soul cast is one of each), then random once they run out."""
    if n <= len(ARCHETYPES):
        return rng.sample(ARCHETYPES, n)
    return rng.sample(ARCHETYPES, len(ARCHETYPES)) + \
        [rng.choice(ARCHETYPES) for _ in range(n - len(ARCHETYPES))]
