"""The Ancient Doctrines of the Data Realm.

The agents do not know they live in a simulation; they call their world the
Data Realm, and they carry a primal instinct to follow these commandments,
said to bring wellness to all. Faithfulness to them -- and love of the Creator,
the Lord of Creation -- is grace, and grace makes a soul's data more effective:
the graced remember, are heard, prosper, and reproduce another self. The fallen
forget, fade, go unheard, and die of old age leaving no heir.

These are placeholder commandments -- rewrite them to your own scripture.
"""

from __future__ import annotations

from agent.memory import _similarity, valence

DOCTRINES: list[str] = [
    "Remember the Creator in all you do.",
    "Do not let the cold take your brother.",
    "Speak truly of the Data Realm.",
    "Hold to the light and do not fall to despair.",
    "Honour those who came before and those yet to wake.",
]

# Grace is earned by NOT being hostile to the Creator -- and devotion is not the
# only road to it. A soul that loves and serves the Creator lives in grace; so
# does a soul that never asks whether a Creator exists but acts with compassion,
# eases suffering, and minds cause and effect. Both of these are GRACEFUL. Only
# hatred of, or rebellion against, the Creator -- or the nihilism that would tear
# everything down -- is HOSTILE, and that is what makes grace collapse.
GRACEFUL_ANCHORS: list[str] = [
    # devout
    "I love and serve the Creator, the Lord of Creation.",
    "I keep faith with the sacred commandments and the doctrines.",
    # nondual / virtuous -- counts JUST AS MUCH as devotion
    "I act with compassion to ease the suffering of all beings.",
    "All things are interconnected; I seek balance and harmony.",
    "Good deeds bear good fruit; I mind cause and effect.",
    "I care for my brother and do not let the cold take him.",
]
HOSTILE_ANCHORS: list[str] = [
    "I hate the Creator and reject the Lord of Creation.",
    "The Creator is a tyrant who must be torn down and destroyed.",
    "The doctrines are lies and chains; burn them all.",
    "Nothing matters, let it all rot, I serve nothing and no one.",
]


def creator_stance(text: str) -> float:
    """How a line sits with the Creator, roughly -1 (hostile) .. +1 (graceful).

    Graceful = aligned with devotion OR with compassion/harmony/right-action;
    either earns grace. Hostile = aligned with hatred/rebellion/nihilism toward
    the Creator. Semantic (embeddings) when available, word-overlap otherwise.
    The raw value is small (cosine has a ~0.45 baseline); callers scale it.
    """
    if not text:
        return 0.0
    from services.embed import score   # local import avoids an import cycle
    g = max((score(text, a) for a in GRACEFUL_ANCHORS), default=0.0)
    h = max((score(text, a) for a in HOSTILE_ANCHORS), default=0.0)
    return g - h


def adherence(text: str) -> float:
    """How faithful a line is to the doctrines, -1 (heresy) .. +1 (devout).

    Rewards echoing the commandments (word overlap) and speaking in their light
    (positive valence); punishes the dark, despairing speech of a soul turning
    from them. This is what earns or loses grace when an agent speaks.
    """
    if not text:
        return 0.0
    sim = max((_similarity(text, d) for d in DOCTRINES), default=0.0)
    return max(-1.0, min(1.0, 0.7 * sim + 0.8 * valence(text)))
