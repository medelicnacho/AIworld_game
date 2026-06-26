"""Identity-threat hostility & ideological laundering -- config + classifier.

DESIGN PRINCIPLE. Hostility is driven by THREAT TO IDENTITY, not by doctrinal
disagreement. Doctrine is a downstream layer that governs how hostility is
EXPRESSED and how it is RATIONALIZED -- never whether it is felt. So a faith that
preaches peace can feel hostility its own creed forbids, and resolve the tension
not by dropping the hostility but by RELABELLING the target as evil/blasphemer,
talking itself soul by soul from compassion into crusade using its own scripture.

This module holds the relationship categories, the single config block (every
threshold/scalar the long-run dynamics depend on -- tunable without touching
logic), and the utterance classifier. The mechanics that consume them live on
the Agent (`_weigh_faith`, laundering, the speech-prompt expression rule).

Maps onto the existing engine: hostility/affinity/conviction/war already live on
`agent/agent.py:Agent`; religions on `agent/religion.py`; similarity on
`services/embed.py`. We change WHAT drives hostility, we don't duplicate it.
"""

from __future__ import annotations

from services import embed

# --- relationship categories (fold into the existing hostility/war state) -----
FELLOW = "fellow"          # default: any soul I am not (yet) at enmity with
DISPUTANT = "disputant"    # we disagree, but it reads as debate, not threat
EVIL = "evil"              # The Path's laundered label for a hated fellow
BLASPHEMER = "blasphemer"  # The Devout's laundered label for a denier
AT_WAR = "at_war"          # open conflict (hostility past WAR_THRESHOLD); derived

SPARED = (FELLOW, DISPUTANT)        # categories doctrine says NOT to harm
SANCTIONED = (EVIL, BLASPHEMER)     # laundered: hostility is now righteous


class Cfg:
    """Every knob the long-run dynamics depend on. Tune here, not in logic."""
    THREAT_MATCH = 0.6         # normalized [0,1] above which a line attacks a fundamental
    PERIPHERAL_MATCH = 0.6     # normalized [0,1] above which a line is on-topic debate
    HOSTILITY_DELTA_SCALE = 2.0    # overall gain on threat*investment*reactivity
    CONVICTION_FROM_THREAT = 0.3   # being attacked hardens conviction
    DISSONANCE_RATE = 0.8      # g(): share of felt hostility that becomes tension toward a spared target
    LAUNDER_THRESHOLD = 2.2    # base (hostility+dissonance) needed to flip a category
    LAUNDER_WARM_FACTOR = 2.5  # warm souls' threshold is up to this much higher
    INVEST_FROM_CONVICTION = 0.55
    INVEST_FROM_DISPOSITION = 0.45
    AFFINITY_SOUR = 0.12       # how much a threat cools affinity
    REACTIVITY_FLOOR = 0.35    # warm/peaceable souls still react this much
    EXPRESS_HOSTILITY_FLOOR = 0.6  # felt hostility above which doctrine must restrain speech


def reactivity(temperament: float) -> float:
    """How hard a threat lands, by disposition. The sim's one temperament axis
    runs bleak/cold(-1) .. bright/warm(+1); the cold are quick to anger, the warm
    are peaceable. Reactivity therefore falls as temperament rises."""
    warmth = (temperament + 1.0) / 2.0        # 0 (cold) .. 1 (warm)
    return Cfg.REACTIVITY_FLOOR + (1.0 - Cfg.REACTIVITY_FLOOR) * (1.0 - warmth)


def launder_threshold(temperament: float) -> float:
    """The (hostility+dissonance) needed to relabel a spared soul as a righteous
    enemy. Warm souls have a far higher bar -- combined with their low reactivity,
    the warmest may never flip a fellow into evil."""
    warmth = (temperament + 1.0) / 2.0
    return Cfg.LAUNDER_THRESHOLD * (1.0 + Cfg.LAUNDER_WARM_FACTOR * warmth)


def base_investment(conviction: float, temperament: float) -> float:
    """How much of the self is staked on faith-membership. Scales hostility (NOT
    doctrine). High conviction and a strong disposition both raise it."""
    inv = (Cfg.INVEST_FROM_CONVICTION * conviction
           + Cfg.INVEST_FROM_DISPOSITION * abs(temperament))
    return max(0.0, min(1.0, inv))


def _normalize(raw: float) -> float:
    """Map a raw similarity to a backend-independent [0,1] strength, so the
    thresholds above mean the same thing under cosine or word-overlap."""
    if embed.using_embeddings():
        return max(0.0, min(1.0, (raw - 0.45) / 0.30))   # cosine 0.45..0.75 -> 0..1
    return max(0.0, min(1.0, raw / 0.5))                 # jaccard 0..0.5 -> 0..1


def classify(utterance: str, anti_axioms, peripherals,
             threat_text: str | None = None) -> tuple[float, float]:
    """Score an incoming line against MY ideology -> (threat, peripheral_overlap),
    each normalized [0,1]. `threat` is how directly it negates a fundamental
    (matched against precomputed anti-axioms, because embeddings give similarity,
    not logical negation); `peripheral_overlap` is relevant-but-safe debate.

    `threat_text` lets the caller match threat against the fundamental a speaker is
    PROCLAIMING rather than its loose spoken paraphrase -- a rival's professed
    fundamental is reliably one of my anti-axioms, where a small model's atmospheric
    wording often is not. Peripheral overlap always uses the literal utterance."""
    tt = threat_text or utterance
    threat = _normalize(max((embed.score(tt, a) for a in anti_axioms), default=0.0)) if tt else 0.0
    periph = _normalize(max((embed.score(utterance, p) for p in peripherals), default=0.0)) if utterance else 0.0
    return threat, periph
