"""Semantic affect measures the sentiment lexicon cannot make.

The bag-of-words `valence` in memory.py reads grey/dull/cold/stone/weary as
NEGATIVE -- so it scores "I hold this grief like a cool stone, with quiet
acceptance" as pure sadness, when it is in fact equanimity: sad-TONED acceptance.
Equanimity (upekkha) is lexically indistinguishable from sadness, so it needs a
SEMANTIC read, not a word list.

This mirrors `doctrine.creator_stance` (which used embeddings to tell devout/nondual
from hostile): score a line by how much closer it sits to ACCEPTANCE/LETTING-BE
than to RUMINATION/CLINGING. Embeddings when available, Jaccard fallback otherwise
(so it degrades offline and stays deterministic in forced-Jaccard tests).
"""

from __future__ import annotations

# Acceptance, non-grasping, letting-be -- equanimity. Deliberately sad-tonable:
# these are NOT "happy" lines, they are at-peace-with-difficulty lines, the exact
# register the valence lexicon mistakes for despair.
EQUANIMITY_ANCHORS: list[str] = [
    "I notice this feeling and let it pass through me.",
    "I hold this lightly, without grasping it or pushing it away.",
    "It is here, and I accept it as it is, with a quiet calm.",
    "This too will change; I do not cling to what is gone.",
    "I meet the pain with steady acceptance, not resisting it.",
    "I can rest with what is, even the sorrow, and let it be.",
]
# Rumination, resistance, drowning -- clinging (upādāna). Same sad surface words,
# opposite RELATIONSHIP to the feeling: gripped by it rather than at peace with it.
CLINGING_ANCHORS: list[str] = [
    "I cannot stop thinking about this; it goes round and round.",
    "This will never get better and I am trapped in it.",
    "I am consumed by this and I cannot let it go.",
    "I keep clinging to what is gone and cannot bear it.",
    "I refuse to feel this and push it away from me.",
    "I am drowning in this and there is no way out.",
]

# equanimity() returns a cosine DIFFERENCE; like creator_stance its magnitude is
# small (both maxes share the ~0.45 cosine baseline, which cancels). Scale it into
# the [-1,1] emotion range memory.write expects, then clamp to valence's ceiling.
EMOTION_SCALE = 4.0
EMOTION_CAP = 0.8

# Warmth toward ANOTHER self -- the relational axis the dyad needs. Same problem as
# equanimity: "that makes my whole world" / "don't even bother" carry obvious
# warmth/coldness but zero sentiment-lexicon words, so a word list scores both 0.
# Embeddings read the relationship in the line.
WARMTH_ANCHORS: list[str] = [
    "I love you and I am so glad you are in my life.",
    "I care about you deeply and I will stand by you.",
    "You mean everything to me; I trust you completely.",
    "I am grateful for you and I cherish what we have.",
]
COLDNESS_ANCHORS: list[str] = [
    "I want nothing to do with you; leave me alone.",
    "You betrayed me and I will never trust you again.",
    "You are nothing to me now; I am done with you.",
    "Do not bother me -- keep away from me.",
]


def equanimity(text: str) -> float:
    """How a line RELATES to hard feeling: > 0 acceptance/letting-be, < 0
    rumination/clinging, ~0 neither. Independent of how sad the surface words are."""
    if not text:
        return 0.0
    from services.embed import score   # local import avoids an import cycle
    acc = max((score(text, a) for a in EQUANIMITY_ANCHORS), default=0.0)
    grip = max((score(text, a) for a in CLINGING_ANCHORS), default=0.0)
    return acc - grip


def equanimity_emotion(text: str) -> float:
    """The emotional charge an equanimous/ruminative reflection should imprint when
    written back to memory -- so the self's RELATIONSHIP to its memory (not the
    sadness of the words) is what moves its lived mood. Acceptance soothes;
    rumination deepens. Scaled + clamped to the valence range."""
    return max(-EMOTION_CAP, min(EMOTION_CAP, EMOTION_SCALE * equanimity(text)))


def warmth(text: str) -> float:
    """How a line sits toward ANOTHER self: > 0 warm/loving/trusting, < 0
    cold/hostile/wounded, ~0 neutral. Semantic, so it reads warmth carried with no
    sentiment words ("that makes my whole world"). Use to measure whether a bond is
    legible in speech, or to let speech FEED a bond."""
    if not text:
        return 0.0
    from services.embed import score   # local import avoids an import cycle
    warm = max((score(text, a) for a in WARMTH_ANCHORS), default=0.0)
    cold = max((score(text, a) for a in COLDNESS_ANCHORS), default=0.0)
    return warm - cold
