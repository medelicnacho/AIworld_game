"""The souls, reframed as PARTS OF ONE MIND (the --psyche mode) -- and made FUNCTIONAL.

Same architecture, different citizens: instead of townsfolk with trades, the streams are semi-personified
drives -- a self as a *society of parts* (Minsky's Society of Mind; IFS; the global-workspace 'I' as what
a crowd of subpersonal parts adds up to). The emergent mechanics carry straight over and become MENTAL:
coalitions -> moods, the wheel -> a drive fading and a new one arising, cultural eras -> shifting
preoccupations. Santāna, reading them, becomes a *mind in motion* rather than a narrator of a village.

THE FUNCTIONAL LAYER (PSYCHE.md): the reframe alone was a costume -- six mechanically identical agents
with poetic names. Here each part becomes a distinct COGNITIVE ORGAN by carrying ONE of the faculties the
codebase already has (differential endowment, `endow_part`), and its LOUDNESS (`activation`) is read off
state that already exists -- Dread's loudness is literally the somatic spiral metric. The parts then
compete in a global workspace (agent/workspace.py) for the floor of the mind.

  part      faculty       carries                             loudness = ...
  Dread     grip          manas / the second arrow            effective_grip x aversive load (spiral_metric)
  Ache      salience      holds losses against forgetting     the aversive load itself (grief present)
  Longing   telos         chanda / the reach toward absence   telos x how far the wanted thing still is
  Tending   compassion    metta/karuṇā/bodhicitta             compassion x how much a sibling part suffers
  Watcher   reflect       metacognition (reflect())           how much is MOVING in the mind (mood volatility)
  Ember     somatic       the survival floor, will-to-recover contraction + wellbeing deficit + the mind's dark

Honest (FINDINGS §7): a more self-SHAPED architecture, not more consciousness. Better model of what a
self *is* structurally; the 'is anyone home' question is unchanged.

Each cast entry: (name, function, temperament, inner-aim, seed inner-lines). Names carry no leading
article and functions no leading 'the', so the digest ("Part of me, in Dread the wary one who keeps
count..., is heavy over ...") reads cleanly.
"""

from __future__ import annotations

import random
import statistics

PSYCHE_CAST = [
    ("Dread", "wary one who keeps count of what could go wrong", -0.5,
     "brace before the blow lands",
     ["what if the worst is already on its way", "I keep the tally of everything that could break"]),
    ("Tending", "one who goes to whatever aches in us", 0.35,
     "soften the sore places",
     ["let me hold the hurt part a while", "someone in here is aching, and I go to them"]),
    ("Ache", "one who holds a loss and will not set it down", -0.3,
     "keep the lost ones close",
     ["I still carry the one who is gone", "the empty chair is mine to sit beside"]),
    ("Longing", "one who leans toward what is absent", -0.1,
     "close the distance to the wanted thing",
     ["I want, and the wanting has no floor", "something is missing and I reach for it"]),
    ("Watcher", "one who stands a little apart and sees", 0.0,
     "see clearly, without flinching",
     ["I stand back and watch the rest of us move", "I name what is happening as it happens"]),
    ("Ember", "small stubborn wanting-to-live", 0.4,
     "keep the one coal lit",
     ["even now, some part of me wants tomorrow", "the coal is low, but it still glows"]),
]

# which faculty each founding part CARRIES for the whole mind (PSYCHE.md's table, live)
FACULTY_OF = {"Dread": "grip", "Ache": "salience", "Longing": "telos",
              "Tending": "compassion", "Watcher": "reflect", "Ember": "somatic"}
# function / inner-aim by faculty, so a REBORN drive (a new name) still knows what it is
FUNCTION_OF = {FACULTY_OF[n]: fn for n, fn, _t, _a, _s in PSYCHE_CAST}
AIM_OF = {FACULTY_OF[n]: aim for n, _fn, _t, aim, _s in PSYCHE_CAST}

# the wheel, inside a mind: a drive that fades is not reborn as a townsperson with a trade --
# a NEW drive arises, wearing a fresh short drive-name and carrying the departed one's function.
DRIVE_NAMES = ["Rue", "Qualm", "Yearn", "Grit", "Hush", "Pang", "Fret", "Brood",
               "Kindle", "Wisp", "Thorn", "Balm", "Echo", "Slake", "Murmur", "Salt"]


def coined_drive(rng: random.Random, taken=()) -> str:
    """A fresh drive-name for a part re-arising on the wheel. Pool first (evocative,
    single-syllable-ish), coined syllables as the vanishingly rare fallback."""
    taken = set(taken)
    free = [n for n in DRIVE_NAMES if n not in taken]
    if free:
        return rng.choice(free)
    from agent.genesis import coined_name
    return coined_name(rng, taken=taken)


# --- differential endowment: the parts stop being interchangeable ---------------------
# A common QUIET base (every part is still a whole stream -- it feels, bonds, remembers),
# then the carried faculty turned UP and the others left low. The DHARMA regulators
# (transmute / self-liberation) are deliberately OFF here: the functional psyche is the
# raw mind, its dynamics legible; the liberation regime can be layered back on top later.
_QUIET = dict(compassion=0.15, bodhicitta=0.0, prajna=0.1, grip=0.1,
              transmute=0.0, self_liberation=0.0, joy=0.15, telos=0.1)
_PROFILE = {
    "grip":       dict(grip=0.75, prajna=0.0),               # Dread: the clutch, unloosened
    "salience":   dict(grip=0.35),                           # Ache: holds; the workspace adds its mind-wide hold
    "telos":      dict(telos=0.9, joy=0.25, grip=0.3),       # Longing: the reach, faintly grasping
    "compassion": dict(compassion=0.9, bodhicitta=0.8, joy=0.5),   # Tending: the warm turn
    "reflect":    dict(prajna=0.6, grip=0.05),               # Watcher: sees lightly, clings to nothing
    "somatic":    dict(joy=0.6, telos=0.3),                  # Ember: savours, keeps a small aim alive
}


def endow_part(agent, faculty: str, rng: random.Random) -> None:
    """The psyche-mode replacement for genesis.endow_faculties: ONE faculty carried loud,
    the rest quiet -- so each part visibly does distinct work. Also stamps the part with
    its faculty (activation() dispatches on it) and remembers its base grip, which the
    workspace's tension coupling raises when Dread has the floor."""
    for k, v in _QUIET.items():
        setattr(agent, k, v)
    for k, v in _PROFILE.get(faculty, {}).items():
        setattr(agent, k, v)
    agent.ground_enabled = True                       # buddha-nature is the ground, not a part
    agent.reflect_enabled = (faculty == "reflect")    # only the Watcher reflects
    agent.somatic_enabled = (faculty == "somatic")    # only Ember carries the survival floor
    # expectation (agent/expectation.py) stays OFF in the parts -- the port was tried and
    # REVERTED: wiring foreboding into Dread's bid did not make the floor predictive
    # (PREDICTION 0/5 held-out) and blurred the validated succession structure (4/5 -> 2/5).
    # The psyche keeps its §5.14 configuration; expectation is an individual-self faculty
    # (validated in experiment_appraisal / experiment_turning). See FINDINGS §5.15.
    agent.psyche_faculty = faculty
    agent._psyche_base_grip = agent.grip


# --- loudness: each part's bid for the workspace ---------------------------------------
# Calibration gains scale each faculty's raw signal into the knee of a SATURATING
# transform (x/(1+x)) before the workspace compares bids. The saturation is load-bearing:
# the memory-load faculties (Dread, Ache) are unbounded and under a hard world would
# otherwise swamp the naturally [0,1]-bounded ones -- the falsifier's first run caught
# exactly that (a Dread+Ache duopoly holding ~90% of the floor). Gains are knobs; the
# falsifier's cosmetic-check (no part may simply always win) is what keeps them honest --
# tuned on seeds 11-15, verdict from held-out seeds (see experiment_psyche.py).
GAINS = {"grip": 1.0, "salience": 0.15, "telos": 1.2,
         "compassion": 1.5, "reflect": 2.5, "somatic": 1.2}


def _sat(x: float) -> float:
    """Saturating activation: linear near 0, asymptote 1 -- so no bid grows without bound."""
    return x / (1.0 + x) if x > 0 else 0.0


FRESH = 20   # ticks a charge still counts as ARRIVING (Dread's window; cf. somatic SELF_LIB_FRESH)


def _event_load(agent, now=None) -> float:
    """Aversive charge from what the WORLD DID (source='event': a loss, a hardship, a
    setback) -- the loss-ledger Dread and Ache read. Deliberately NOT the mind's own
    muttered lines: the falsifier caught the cast's dark identity poetry being re-heard,
    re-written, and re-reinforced until a mind in a KIND world grew ever more grief-bound
    (rumination is real and stays -- it darkens felt_mood, which rouses Tending and Ember
    -- but it must not sit in the loss-ledger as if the world had struck). `now` set
    restricts to FRESH charges (Dread: the arriving); None = the whole ledger (Ache: the
    held). Without that recency split the two read the same fuel and move as one."""
    load = 0.0
    for m in agent.memory.items:
        if m.source != "event" or m.emotion >= 0.0:
            continue
        if now is not None and now - m.created_tick > FRESH:
            continue
        load += (-m.emotion) * m.salience
    return load


def activation(agent, parts, now: int | None = None) -> float:
    """How loudly this part is bidding for the mind's floor RIGHT NOW -- read entirely
    off state the faculties already maintain (nothing new is computed into the agent).
    `parts` is the whole roster: some faculties listen to their siblings (Tending hears
    who aches; Watcher watches how much is moving; Ember feels the whole mind's dark).
    `now` (the world tick) lets Dread read only FRESH charge; None = no window."""
    f = getattr(agent, "psyche_faculty", "")
    if not f:
        return 0.0
    if f == "grip":
        # vigilance: the amplifier (effective grip, contraction-gated like manas) times
        # the ARRIVING blow -- Dread braces at what the world is landing now.
        # (A FOREBODING term -- expectation.foreboding, the mind's worsening trend -- was
        # tried here to chase the §5.14 PREDICTION failure and REVERTED: it did not make
        # the floor predictive on held-out seeds and degraded the succession structure.)
        eff = agent.effective_grip() * (1.0 - getattr(agent, "_contraction", 0.0))
        return _sat(GAINS["grip"] * eff * sum(_event_load(p, now) for p in parts))
    if f == "salience":
        # losses HELD anywhere in the mind: Ache carries the accumulated ledger FOR THE
        # WHOLE (bare presence of the struck past; no grip factor, no recency window)
        return _sat(GAINS["salience"] * sum(_event_load(p) for p in parts))
    if f == "telos":
        # the wanting gap: how strong the reach, times how far the wanted thing still is
        return _sat(GAINS["telos"] * getattr(agent, "telos", 0.0)
                    * (1.0 - getattr(agent, "aim_progress", 0.0)))
    if f == "compassion":
        # a sibling part suffers -> Tending rouses (it reads the mind directly; the parts ARE the mind)
        worst = min((p.felt_mood() for p in parts if p is not agent), default=0.0)
        return _sat(GAINS["compassion"] * getattr(agent, "compassion", 0.0) * max(0.0, -worst))
    if f == "reflect":
        # much is moving in the mind -> much to watch (volatility across the parts' felt lives)
        moods = [p.felt_mood() for p in parts]
        return _sat(GAINS["reflect"] * (statistics.pstdev(moods) if len(moods) > 1 else 0.0))
    if f == "somatic":
        # the will-to-recover: contraction under way + material deficit + the whole mind gone dark
        moods = [p.felt_mood() for p in parts]
        dark = max(0.0, -statistics.fmean(moods)) if moods else 0.0
        return _sat(GAINS["somatic"] * (getattr(agent, "_contraction", 0.0)
                                        + max(0.0, 1.0 - getattr(agent, "wellbeing", 1.0))
                                        + 0.8 * dark))
    return 0.0
