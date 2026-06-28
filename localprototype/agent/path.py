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
