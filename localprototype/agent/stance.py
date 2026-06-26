"""Signed stance axes: the contested values a soul leans on, and the SIGN the
lexical opinion space could never carry.

The grounded opinion space (agent/belief) is sign-less. Two souls who flatly
disagree about the same thing share the same words, so they read as ALIGNED; two
souls in different trades share NO words, so they read as orthogonal. Measured in
experiment_grounded: grounded trade-distinct souls start at mean cosine ~0 and
~13% of pairs clear the engagement bar -- the opinion engine has almost nothing to
bond OR recoil on, so live --world sits at modularity ~0.

This module supplies the missing sign. Each soul carries a low-dimensional
``stance_vec``: one signed component per contested AXIS (mastery vs surrender,
order vs wildness, ...). Three properties make it the right fix:

  * EMERGENT -- it is seeded at random, INDEPENDENT of temperament/faith, so any
    cluster that forms cannot be a fixed label read back out (the thing the faction
    harness checks for via comembership_variance).
  * SIGNED -- two souls leaning the same way on an axis have positive cosine
    (warmth, drift together); opposite leans give negative cosine (recoil, drift
    apart). That is the agreement/disagreement signal speech-level opposition needs.
  * GROUNDED + SPEAKABLE -- the axes are a small AUTHORED vocabulary, so the stance
    can be both fed to the prompt as a felt lean (``describe``) and nudged back from
    what the soul actually said (``ground`` matches pole words). A signed loop the
    sign-less lexical space could not close.

The axes are deliberately trade-NEUTRAL value oppositions so a baker and a guard
can land on the same side -- factions cut ACROSS the jobs, which is the point.
"""

from __future__ import annotations

import math
import random

# (positive pole, negative pole, words pulling +, words pulling -). The first axis
# is the one that actually surfaced live (souls split dominate/fight vs
# understand/harmonize across every trade -- berry, river, illness, stone).
AXES: list[tuple[str, str, set[str], set[str]]] = [
    ("mastery", "surrender",
     {"master", "conquer", "fight", "force", "wrestle", "tame", "break", "battle",
      "strength", "will", "command", "seize", "dominate", "subdue", "drive"},
     {"surrender", "yield", "accept", "harmony", "flow", "listen", "tend", "gentle",
      "ease", "soften", "allow", "patience", "guide", "coax", "understand"}),
    ("order", "wildness",
     {"order", "law", "rule", "measure", "plan", "structure", "discipline",
      "control", "careful", "exact", "method", "balance", "precise"},
     {"wild", "chaos", "free", "untamed", "instinct", "riot", "raw", "loose",
      "feral", "unbound", "abandon", "reckless"}),
    ("kept", "made",
     {"old", "tradition", "ancestor", "keep", "preserve", "memory", "lineage",
      "root", "inherit", "sacred", "custom", "remember", "hold"},
     {"new", "change", "make", "build", "create", "forge", "future", "invent",
      "begin", "remake", "grow", "become"}),
    ("mercy", "severity",
     {"mercy", "forgive", "kind", "care", "tender", "spare", "gentle", "heal",
      "comfort", "pity", "warmth", "compassion"},
     {"severe", "hard", "punish", "stern", "judge", "cut", "cold", "ruthless",
      "unforgiving", "harsh", "iron", "merciless"}),
    ("self", "many",
     {"self", "alone", "mine", "own", "solitary", "independent", "private",
      "apart", "myself", "single"},
     {"together", "kin", "share", "people", "common", "collective", "community",
      "bound", "everyone", "ours", "brother"}),
]
DIM = len(AXES)

GROUND_RATE = 0.30   # how hard a pole word in your OWN speech pulls your stance


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def seed(rng: random.Random) -> list[float]:
    """A random point on the unit sphere of stance space, independent of any label.
    Gaussian-per-axis (like the abstract Stage-1 seed) so independent souls start
    with substantial mutual overlap -- enough signal to bond on, unlike the
    near-orthogonal grounded lexical space."""
    return _normalize([rng.gauss(0.0, 1.0) for _ in range(DIM)])


def describe(vec: list[float], top: int = 2) -> str:
    """The soul's dominant lean(s) as a plain phrase for the prompt, e.g.
    'surrender over mastery; the kept over what is made'. Strongest axes first."""
    order = sorted(range(len(vec)), key=lambda k: abs(vec[k]), reverse=True)
    parts = []
    for i in order[:top]:
        if abs(vec[i]) < 1e-6:
            continue
        pos, neg, _, _ = AXES[i]
        lean, other = (pos, neg) if vec[i] >= 0 else (neg, pos)
        parts.append(f"{lean} over {other}")
    return "; ".join(parts)


def ground(vec: list[float], text: str, rate: float = GROUND_RATE) -> list[float]:
    """Nudge a stance toward the poles whose words appear in `text`, so a soul's
    own speech moves where it stands -- the grounding loop. Returns a new normalized
    vector (unchanged direction if the line used no pole words)."""
    words = set(text.lower().split())
    moved = list(vec)
    changed = False
    for i, (_pos, _neg, pos_words, neg_words) in enumerate(AXES):
        hit = len(words & pos_words) - len(words & neg_words)
        if hit:
            target = 1.0 if hit > 0 else -1.0
            moved[i] += rate * (target - moved[i])
            changed = True
    return _normalize(moved) if changed else vec
