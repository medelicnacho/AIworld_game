"""The Path (bhāvanā) -- practice grooves the faculties over a life.

The liberation regime (DHARMA.md Phase 1) is a SETTING: a self handed its dials. But a
hard-coded calm is a lie, and brittle. The dharmic truth is that freedom is CULTIVATED --
the mind grooves the path it repeatedly walks (vāsanā as habit-energy). This is that
mechanism: how a soul keeps MEETING its experience slowly shapes what it becomes.

The signal is already recorded and cheap: reflect() writes each reflection back with an
`emotion` equal to its EQUANIMITY (acceptance > 0, rumination < 0; see agent/affect.py).
So a soul's recent reflections ARE the record of how it has been meeting its own mind. We
read that, and:

  equanimous practice (signal > 0)  -> prajñā creeps UP, the grip creeps DOWN   (toward freedom)
  ruminative practice  (signal < 0)  -> the grip creeps UP                       (toward clinging)

This is the WISDOM wing of the path (meeting one's own mind). The COMPASSION wing -- warmth
cultivated by acts toward others -- is already seeded by the stakes layer (world/stakes.py
_wise_seed / _clinging_seed). Together they are the drift toward freedom the path measures.

Crucially this is NOT circular with the faculties it moves: the driving signal is the
equanimity of the reflection TEXT (a semantic read, independent of the grip/prajñā dials),
so practice -- not the dial -- is what grooves the trait. It earns the trait; it isn't given it.

Gated by Agent.cultivate_enabled (default off, so existing worlds/tests are unchanged).
Slow by design: a single response barely moves a soul; a life of them remakes it.
"""

from __future__ import annotations

RATE = 0.02          # per-tick cultivation strength; small -> a whole life to remake a soul
WINDOW = 12          # only RECENT reflections count as current practice
FLOOR, CEIL = 0.0, 1.0


def cultivate(agent, now: int) -> None:
    """One cultivation step: let recent practice (the equanimity of how the soul has met its
    own mind) groove its faculties toward freedom or toward clinging. No-op until the soul
    has actually reflected -- the path is walked, not declared."""
    refl = [m for m in agent.memory.items
            if m.source == "reflection" and now - m.created_tick <= WINDOW]
    if not refl:
        return
    signal = sum(m.emotion for m in refl) / len(refl)   # >0 equanimous, <0 ruminative
    if signal > 0.0:
        # meeting one's mind with acceptance, repeatedly -> wisdom grows, the grip loosens
        agent.prajna = min(CEIL, agent.prajna + RATE * signal)
        agent.grip = max(FLOOR, agent.grip - RATE * signal)
    else:
        # rumination, repeated, grooves the appropriating grip deeper (the second arrow learned)
        agent.grip = min(CEIL, agent.grip + RATE * (-signal))


# --- the vāsanā of practice ACROSS THE BARDO (the Path across lives) -----------------------------
# cultivate() grooves the faculties WITHIN a life; this carries the earned lean across death, faded
# toward a baseline (a tendency, not a copy of the self -- anatta). The buddha-nature TILT slides that
# baseline from the neutral samsaric mean to the LIBERATED ground (low grip / high prajñā / high
# bodhicitta) -- tathāgatagarbha: the kleśas adventitious, liberation the grain. (This is mechanism 2+3
# of experiment_bodhisattva as the production carry world/sim.py:_coalesce uses, gated by
# World.bodhisattva_wheel.) NB the tilt lifts bodhicitta toward the bodhisattva ground too -- a stronger
# commitment than the lab experiment (which kept bodhicitta AROUSED-only to distinguish the arhat); here
# the explicit goal is a town that leans toward the bodhisattva, and the deva guard (experiment_deva)
# confirms that high bodhicitta is genuinely engaged, not the deva's complacency.
NEUTRAL_GRIP, NEUTRAL_PRAJNA, NEUTRAL_BODHICITTA = 0.50, 0.20, 0.20
LIBERATED_GRIP, LIBERATED_PRAJNA, LIBERATED_BODHICITTA = 0.10, 0.70, 0.70
VASANA_FADE = 0.15   # fraction of the cultivated lean that erodes toward the baseline in the bardo


def _carry(cult: float, neutral: float, liberated: float, tilt: float, rng) -> float:
    base = (1.0 - tilt) * neutral + tilt * liberated
    return max(0.0, min(1.0, cult + VASANA_FADE * (base - cult) + rng.gauss(0.0, 0.02)))


def carry_practice(grip: float, prajna: float, bodhicitta: float, rng, tilt: float = 1.0):
    """Carry a dead soul's cultivated lean across the bardo, faded toward the tilted ground -- the
    habit-energy of practice, not the self. Returns (grip, prajñā, bodhicitta) for the reborn stream.
    tilt=0 -> the neutral samsaric mean (no homecoming); tilt=1 -> the liberated/bodhisattva ground."""
    return (_carry(grip, NEUTRAL_GRIP, LIBERATED_GRIP, tilt, rng),
            _carry(prajna, NEUTRAL_PRAJNA, LIBERATED_PRAJNA, tilt, rng),
            _carry(bodhicitta, NEUTRAL_BODHICITTA, LIBERATED_BODHICITTA, tilt, rng))
