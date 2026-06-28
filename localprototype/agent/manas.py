"""manas -- the appropriating grip (kliṣṭa-manas / upādāna), a toggleable faculty.

The system already CONSTRUCTS a self (genesis, conviction, the self-model loop) and
MEASURES the relationship to feeling (affect.equanimity). What it lacked is the
distinct move that takes the feeling-stream and clamps it as I / me / mine -- the grip
that fires the "second arrow" (the suffering ADDED by appropriation, on top of the bare
feeling-tone). This is that faculty, and crucially it is built so it can be RELEASED:
grip = 0 is the default, and is exactly the non-appropriative (equanimous) regime.

Operationalisation -- a per-tick transform on the MEMORY stream, gated by self-relevance,
deliberately NOT on the reflect/affect read (so it is not circular with the rumination
affect.py already detects; manas is upstream, affect is the independent downstream
observer). Two effects, scaled by grip strength g in [0,1] and a memory's self-relevance:

  HOLD          self-relevant memories resist decay -- the grip won't let go of what
                is "mine," and the held memory looms larger.
  SECOND ARROW  aversive (emotion < 0) self-relevant memories have their charge
                magnified -- the added suffering of "this is happening to ME."

Distinct from CONSTRUCTION (which writes self-content): manas writes nothing; it refuses
to let self-content decay and magnifies its aversive charge. Hold the construct fixed,
vary g -- that isolation is the experiment (a self with conviction-but-no-grip vs the
same self with conviction-and-grip).

Prediction (measured by the existing grief harness): grip ON suppresses HABITUATION
(the wound won't fade) and drives equanimity down; releasing it lets recovery resume.
"""

from __future__ import annotations

HOLD = 0.05          # how hard the grip resists a self-relevant memory's decay (per tick)
AMP = 0.03           # how fast it amplifies an aversive self-relevant memory's charge
CRAVE = 0.04         # rāga: how fast clutching a PLEASANT charge drains its sweetness (the treadmill)
TRANSMUTE_RATE = 0.15  # Vajrayāna: how fast the grip's energy METABOLIZES the charge to clarity
SELF_SOURCES = {"self", "reflection"}   # the soul's own self-statements are self-relevant by origin

# Self-relevance read (like affect/warmth): how much a line is about "me / mine / what
# is happening to me" vs impersonal world-stuff. Semantic, because "your dearest friend
# has died" is intensely self-relevant with no first-person words in it.
SELF_ANCHORS: list[str] = [
    "this is happening to me; it is mine.",
    "my own life, my loss, my friend, someone I love.",
    "I, myself, who I am and what is mine.",
]
IMPERSONAL_ANCHORS: list[str] = [
    "the weather, the market, the day's ordinary work.",
    "stones, grain, tools, and the passing carts.",
    "general facts about the world out there.",
]


def self_relevance(text: str) -> float:
    """> 0 when a line is about me/mine, < 0 when it is impersonal world-stuff."""
    if not text:
        return 0.0
    from services.embed import score   # local import avoids an import cycle
    s = max((score(text, a) for a in SELF_ANCHORS), default=0.0)
    o = max((score(text, a) for a in IMPERSONAL_ANCHORS), default=0.0)
    return s - o


def relevance_of(memory) -> float:
    """A memory's self-relevance: semantic when embeddings are up, with a floor for the
    soul's own self-statements; source-only fallback when they're down (deterministic)."""
    from services import embed
    if embed.using_embeddings():
        r = self_relevance(memory.text)
        if memory.source in SELF_SOURCES:
            r = max(r, 0.5)
        return r
    return 1.0 if memory.source in SELF_SOURCES else 0.0


def apply(agent, now: int) -> None:
    """One grip cycle, after memory has decayed: hold self-relevant memories against
    decay and amplify aversive ones. No-op when grip is 0 (the released / equanimous
    default). Never writes content -- it only re-weights what is already there."""
    # the grip's hold after wisdom: prajñā loosens it at the source (see effective_grip)
    g = agent.effective_grip() if hasattr(agent, "effective_grip") else getattr(agent, "grip", 0.0)
    if g <= 0.0:
        return
    for m in agent.memory.items:
        if m.source == "doctrine":
            continue
        r = relevance_of(m)
        if r <= 0.0:
            continue
        # HOLD: the self stays PRESENT to the charged memory (salience held). This is the
        # engagement -- shared by clinging AND transmutation; only RELEASE (prajñā lowering
        # the effective grip) lets it fade. So transmutation is the third path: it does not
        # disengage, it stays in full contact.
        m.salience = min(1.0, m.salience * (1.0 + g * r * HOLD))
        tr = getattr(agent, "transmute", 0.0)
        if m.emotion < 0.0:
            if tr > 0.0:
                # TRANSMUTE (Vajrayāna): the gripping energy, recognized, METABOLIZES the
                # aversive charge into clarity rather than deepening it -- aversion -> mirror-
                # like seeing. Stays present (salience held) yet the wound is digested, not
                # amplified: engaged AND unwounded, the tantric result.
                m.emotion *= (1.0 - TRANSMUTE_RATE * tr)
            else:
                # SECOND ARROW: aversive self-relevant tone magnified by being gripped as mine
                m.emotion = max(-1.0, m.emotion * (1.0 + g * r * AMP))
        elif m.emotion > 0.0:
            # a PLEASANT charge. Under transmutation (or joy) it is simply SAVORED -- held and
            # received as warmth, nothing to grasp. But a bare clutching grip CRAVES it (rāga):
            # clinging to the good as "mine to keep" drains its present sweetness -- the hedonic
            # treadmill, where having a thing is not the same as enjoying it.
            jo = getattr(agent, "joy", 0.0)
            if tr <= 0.0 and jo <= 0.0:
                m.emotion = max(0.0, m.emotion * (1.0 - g * r * CRAVE))
