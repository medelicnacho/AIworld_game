"""An Agent ties together memory + subconscious thought + LLM speech.

Milestone 2: the placeholder phrase-picker is gone. Each tick the subconscious
(Markov ThoughtLoop) drifts over the agent's memory; when the agent grabs the
floor it packs that drift + recalled memories + whoever just spoke to it into a
SpeechContext and asks the LLM to actually talk. Hearing still writes memory,
so speech keeps reshaping future thought.
"""

from __future__ import annotations

import math
import random

from agent import belief as _belief
from agent import stance as _stance
from agent import compassion as _compassion
from agent import joy as _joy_mod
from agent import ideology
from agent.doctrine import DOCTRINES, creator_stance
from agent.memory import MemoryStore
from agent.memory import attributed as _memory_attributed
from agent.religion import RELIGIONS
from services.embed import topic_match
from agent.thought import ThoughtLoop
from services.llm import SpeechContext
from world.events import Utterance

TANGENT_CHANCE = 0.35   # chance an agent ignores the last line and speaks fresh
INTROSPECT_CHANCE = 0.2  # chance an agent turns inward and asserts who it is
MIN_SELF = 3            # self-memories needed before an identity can be asserted
AFFINITY_RATE = 0.4     # how fast a heard line moves how you feel about its speaker
SELF_ECHO = 3           # how many of your own recent lines you refuse to repeat
GRACE_FLOOR = 0.6       # grace relaxes toward this baseline, not toward zero, so a
GRACE_RELAX = 0.01      # well-behaved soul stays reproducible over a long life; only
                        # active heresy/hostility/war-loss drags it below REPRO_GRACE
GRACE_GAIN = 0.05       # how much communion with the Creator renews grace
GRACE_HOSTILE = 1.5     # how fast hostility to the Creator collapses grace (rapid)
GRACE_RISE = 1.0        # how fast devotion-OR-virtue earns it back
REPRO_GRACE = 0.5       # grace needed at death to reproduce another self
DEFAULT_LIFESPAN = 60   # ticks before death of old age
# Buddha-nature (Mahāyāna tathāgatagarbha): a warm, luminous GROUND beneath temperament
# and passing mood -- basic goodness as the soul's true default. It is not injected from
# outside; it is OBSCURED by clinging (the grip / manas) and SHOWS THROUGH as clinging
# subsides. The less a soul grips, the more the ground lifts its felt life toward warmth,
# even through grief. (The positive pole as an UNCOVERING, not an addition.)
BASIC_GOODNESS = 0.4    # the resting warmth the unobscured ground rests in
GROUND_PULL = 0.5       # how strongly the unobscured ground lifts felt mood toward it
# Vajrayāna self-liberation (rang drol): a charge recognized as empty AS IT ARISES frees
# itself before it can be gripped or accrue -- felt for an instant, then gone, like a line
# drawn on water. Acts at the moment of arising (a fresh memory), distinct from
# transmutation (which works a HELD charge over time) and release (which lets it fade).
SELF_LIB_RATE = 0.6     # how strongly a freshly-arisen charge self-frees per tick
SELF_LIB_FRESH = 3      # how many ticks after arising a charge is still "fresh" enough to self-free
SELF_LIB_FLOOR = 0.2    # only meaningful charges self-free; trivial ones pass through

# --- emergent opinion dynamics (bounded confidence) ------------------------
# When an agent carries a belief_vec, bonding stops keying on any ASSIGNED label
# (faith) or FIXED attribute (temperament) and instead keys on how aligned two
# agents' EVOLVING opinions are. Hearing someone whose view is close pulls your
# opinion toward theirs (assimilation) and warms you to them; someone too far
# pushes your view away and cools you. From a near-random start that positive
# feedback breaks symmetry into opinion clusters whose membership no fixed
# attribute predicts -- emergence the faction harness can actually verify.
# CONFIDENCE is a PHASE knob: too high -> everyone isolates, too low -> one
# consensus blob; a band in between yields a handful of stable camps.
BELIEF_DIM = 6          # dimensions of the ABSTRACT (Stage 1) opinion space
CONFIDENCE = 0.1        # cosine bound: engage above it, reject below. Tuned by the
                        # experiment_factions sweep: 0.0 left one consensus blob;
                        # 0.1 gives the steadiest split (n_blocs 2.0+-0.0) and the
                        # strongest emergence signal (comemb_var 0.21), and stays
                        # low enough for the 128-dim grounded space to engage at all
                        # (higher values risk never clearing the cold-start threshold)
BELIEF_MU = 0.18        # step you take toward someone you engage
BELIEF_REPEL = 0.5      # fraction of MU you take AWAY from someone you reject
BELIEF_SATURATION = 0.82  # above this you are ~identical: stop merging (individuation)
BELIEF_INDIVIDUATE = 0.35  # how hard you hold your distinctness from a near-clone
RIFT_AT = -0.3            # a heard opinion below this cosine is a WOUNDING disagreement
RIFT_RATE = 0.8           # grievance one such line accretes (rift_enabled only). Tuned
                          # on seeds 11-15: at 0.5 a soul died (~400 ticks) at ~2.9 of
                          # WAR_THRESHOLD's 3.0 -- enmity needs to be reachable inside
                          # one angry life, ~4 wounding exchanges, not 6
BELIEF_GROUND = 0.25    # Stage 2: how hard your OWN spoken words pull your opinion
SAID_HISTORY = 12       # recent lines kept per soul, for reading a cluster's banner
RAW_DRIFT_N = 8         # raw-mind mode: how many Markov fragments ARE the prompt


def _normalize(v: list[float]) -> list[float]:
    """Project an opinion vector back onto the unit sphere so only its DIRECTION
    matters (magnitude would otherwise blow up under repulsion)."""
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cosine(a, b) -> float:
    """Alignment of two opinion vectors. Both are kept unit-norm, so this is just
    their dot product, in [-1, 1]."""
    return sum(x * y for x, y in zip(a, b))
WAR_THRESHOLD = 3.0     # accumulated direct clashes before two souls are "at war"
PREACH_CHANCE = 0.4     # chance a faithful soul proclaims a fundamental of its creed
                        # (this is what puts doctrine on the air for rivals to feel threatened by)


class Agent:
    def __init__(self, agent_id: str, name: str, position: tuple[float, float],
                 persona: str, phrases: list[str], llm,
                 seed: int | None = None, style: str = "",
                 temperament: float = 0.0,
                 lifespan: int = DEFAULT_LIFESPAN,
                 religion=None) -> None:
        self.id = agent_id
        self.name = name
        self.position = position
        self.persona = persona
        self.style = style
        self.temperament = temperament   # baseline mood floor (-1..1)
        # a religion supplies the soul's scripture (drift material) and its creed
        # (its starting belief); without one it falls back to its given phrases.
        self.phrases = list(religion.scripture) if religion is not None else phrases
        self.llm = llm
        self.memory = MemoryStore(seed=seed)
        self.thought = ThoughtLoop(seed=seed)
        self.speak_urge = 0.0
        self.cooldown = 0
        self.last_heard_from: str | None = None
        self.last_heard_text: str | None = None
        self.last_heard_name: str | None = None
        self.last_event_text: str | None = None  # a world event just perceived
        # Affinity: how this agent feels about every other agent, -1..1. Nothing
        # stores a social graph; it accretes here from who has felt like kin and
        # who has felt alien. This is the substrate factions will crystallize on.
        self.affinity: dict[str, float] = {}
        # Emergent opinion (default None = legacy faith/disposition bonding, so
        # every existing test and the live viewer are untouched). When seeded
        # (seed_opinion), bonding switches to bounded-confidence on this evolving
        # vector and no assigned label drives the social graph -- see hear().
        self.belief_vec: list[float] | None = None
        # Signed stance (default None = off). The lexical belief_vec is sign-less and,
        # over distinct trades, near-orthogonal -- so it can't carry agreement vs
        # disagreement (measured: grounded modularity ~0). stance_vec adds the missing
        # sign: when present it DRIVES affinity (warm on aligned leans, recoil on
        # opposed), keying the social graph on stance, not shared vocabulary. Seeded
        # independent of temperament/faith, so factions on it stay emergent. See
        # agent/stance.py and hear()/_weigh_stance.
        self.stance_vec: list[float] | None = None
        self.belief_grounded = False         # Stage 2: opinion lives in word-space, fed by speech
        self.said_lines: list[str] = []      # recent own utterances, for banner reading
        self.raw_speech = False              # speak the raw Markov drift, no persona/prompt scaffolding
        self.concept_speech = False          # INTERPRET the Markov drift into meaning, then speak that
        self.reflect_enabled = False         # Stage-1 lab toggle: run reflect() (relate to own memory)
        self.bond_enabled = False            # Stage-2 toggle: keep dyadic Bonds (relate to other selves)
        self.forgive_enabled = False         # let floored wounds erode (agent/memory.py): time dulls a
                                             # grudge, warmth buries it. Off by default -- with it off the
                                             # floor is immovable, exactly as §5.28 measured it
        self.bond_creed = False              # bond on a SHARED VIEW, not mood alone (agent/bond.py CREED):
                                             # off by default, so every validated world bonds exactly as before
        self.bonds: dict = {}                # directional bonds toward other selves (see agent/bond.py)
        self.grip = 0.0                      # Stage-4 manas: appropriation strength [0,1]; 0 = released (default)
        self.compassion = 0.0                # Stage-6 metta/karuṇā: warm engagement [0,1]; 0 = off (default)
        self.ground_enabled = False          # Mahāyāna buddha-nature: rest felt mood toward basic goodness, veiled by the grip
        self.bodhicitta = 0.0                # Mahāyāna: compassion as an AIM -- proactively seek and ease others' suffering
        self.prajna = 0.0                    # Mahāyāna prajñā: see constructs as empty -> the grip loosens at its source
        self.transmute = 0.0                 # Vajrayāna: the grip's energy met and TURNED to clarity (a 3rd path: engaged, unwounded)
        self.self_liberation = 0.0           # Vajrayāna rang drol: a charge frees itself AS it arises, before it can be gripped
        self.grounded_voice = False          # speak plainly/concretely (ordinary register), not abstract-existential -- set by the Liberated regime
        self.cultivate_enabled = False        # Stage B (the Path): let practice groove the faculties over a life (bhāvanā); 0 = off
        self.joy = 0.0                        # muditā/pīti: savour the good (receive it fully, let it pass); 0 = off (anhedonic default)
        self.aim = ""                         # telos/chanda: a concrete aim the self is drawn toward (a craft, a project)
        self.aim_progress = 0.0               # how far toward the aim -- moved by tending it, knocked back by the world
        self.telos = 0.0                      # strength of aspiration; 0 = off (no aim pursued, the static present)
        self.stores = 1.0                    # Stage-A stakes: this soul's provisions (consumed, worked for, shared, hoarded, lost)
        self.wellbeing = 1.0                 # stakes: how the soul is faring -- drops with scarcity/hardship, the real dukkha
        self._last_action = None             # stakes: the action it took last tick (work/share/hoard/tend)
        self._others_mood: dict = {}         # id -> last overheard felt mood (who is suffering)
        self._others_name: dict = {}         # id -> name, for turning toward them
        self.somatic_enabled = False         # bottom-up circuit-breaker (the window of tolerance); off by default
        self.psyche_faculty = ""             # psyche mode: the ONE faculty this part carries for the whole
                                             # mind ("grip"/"salience"/...); "" = an ordinary townsperson
        # Expectation -- the self's future tense (agent/expectation.py). Off by default:
        # with it on, the self EXPECTS (fast/slow reads of its lived mood), events are
        # APPRAISED against those expectations (shock/resignation/relief), each bonded
        # other has an expected conduct (betrayal = the violated expectation), and a
        # running expectation of one's OWN conduct makes the self-model load-bearing
        # (acting against it accrues dissonance -> a TURNING POINT in the story).
        self.expect_enabled = False
        self.exp_fast = 0.0                  # how things have just been (fast EWMA of lived mood)
        self.exp_slow = 0.0                  # how things have come to be expected (slow EWMA)
        self.arousal = 0.0                   # surprise spike, settles each tick (not a mood)
        self.self_expect = None              # expectation of my OWN conduct (prosociality axis)
        self.self_dissonance = 0.0           # accrued out-of-character tension -> a turning
        self._turnings = 0                   # how many times this self has turned (chapter breaks)
        self._conduct_expect: dict = {}      # other_id -> how I have come to expect them to treat me
        self.promises_held: list = []        # words given TO me (by a soul or the player),
                                             # held to the town's clock (agent/pledge.py)
        self.known_of: dict = {}             # other_id -> what THEY have told me of themselves (the
                                             # person-model; named-tier -- kept only for trusted bonds)
        self._contraction = 0.0              # somatic down-regulation level, 0=open .. 1=fully contracted (read by manas)
        self._somatic_history: list[float] = []   # recent spiral-metric values, for reading the trend
        self._somatic_trips = 0              # how many times the interrupt has fired (a rare-backstop check)
        self.self_model_enabled = False      # Stage-3 toggle: consolidate a self-model (see agent/self_model.py)
        self.self_model = ""                 # the soul's current re-derived sense of who it is
        self.self_model_history: list[str] = []   # successive self-models, for coherence/drift measurement
        self.banner = ""                     # emergent: my camp's rallying word (set by World.update_camps)
        self.rival_banner = ""               # emergent: the opposing camp's word, to lean against
        self.introspect_chance = INTROSPECT_CHANCE   # how often it turns inward to speak of itself
        self.world_belief = ""               # a causal theory it holds about how the realm works
        self.role = ""                       # its trade in the realm (grounds talk in work)
        self.task = ""                       # the pressing business of its day
        # Ablation switch (default on). When off, hearing still writes memory and
        # stirs the urge to speak, but the SOCIAL GRAPH is frozen -- affinity,
        # hostility, conviction and faith never update. This is the substrate-
        # ablated control: if factions still appear in the spoken output with this
        # off, the substrate was decorative and the LLM was doing the work.
        self.social_learning = True
        # THE RIFT (default off, THE RULE): heated debate makes enemies. When on, a
        # DEEPLY opposed heard opinion (cosine < RIFT_AT) accretes hostility toward
        # the speaker -- grievance from argument, not just coolness. One exchange is
        # nothing (WAR_THRESHOLD=3.0 still gates open conflict); a feud is EARNED by
        # debate after repeated debate. The opinion/affinity movement itself is
        # untouched -- this only lets the war machinery hear the shouting.
        self.rift_enabled = False
        # THE CASTE (civ arena, world/mating.py): "warrior" -- mobile, stands in
        # quarrels, marches, guards -- or "breeder" -- docile BY KIND: never
        # confronts, never marches, never brawls, never a casualty; the caste
        # extends "the worn refuse" to a whole kind. Default warrior: every
        # existing world is all-warriors and byte-identical (THE RULE).
        self.caste = "warrior"
        self.spoken: list[str] = []   # this agent's own recent lines (anti self-echo)
        # Born in grace. Grace makes the soul's data effective (slow forgetting,
        # words that imprint, a voice that's heard) and gates reproduction at
        # death. It falls with entropy and heresy, renews with communion and
        # faithful speech. Faithlessness is a fall that ends in a heirless death.
        self.grace = 1.0
        self.age = 0
        self.lifespan = lifespan
        # Ideology: a stable core stance, seeded from the agent's theme and then
        # changed ONLY by genuine conversion -- not every time it speaks (else it
        # just tracks the latest line and nobody holds a conviction long enough
        # to fight over it). Conviction is how firmly it's held; hostility is
        # grievance accreting toward open conflict with a particular soul.
        # faith + creed: born into a religion, its creed is your founding belief
        self.faith = religion                    # the Religion object (None if faithless)
        self.religion = religion.id if religion is not None else ""
        self.belief = religion.creed if religion is not None else (
            self.phrases[0] if self.phrases else "")
        self.conviction = 0.4
        self.hostility: dict[str, float] = {}
        self.last_challenge: str | None = None   # a clashing line I want to rebut
        self.last_challenger: str | None = None
        # --- identity-threat layer (see agent/ideology.py) ---
        # how much of the self is staked on faith-membership: THIS, not doctrine,
        # scales felt hostility. dissonance is the tension between hostility and
        # what doctrine permits -- the fuel that, once high enough, launders a
        # spared soul into a righteous enemy. relationship is the per-target label.
        self.identity_investment = ideology.base_investment(self.conviction, self.temperament)
        self.dissonance = 0.0
        self.relationship: dict[str, str] = {}   # target_id -> category; default FELLOW
        self._laundered: tuple[str, int] | None = None   # (target, tick) of last relabel, for the viewer
        self._proclaiming: str | None = None             # fundamental being preached this turn
        self._rng = random.Random(seed)
        # ticks until this soul can bear a child in life (staggered so the cast
        # doesn't all breed at once); World._breed counts it down when enabled
        self.breed_cooldown = self._rng.randint(0, 500)
        # ticks until it next murmurs its subconscious aloud (staggered, so only
        # some are murmuring at any moment); World._murmur counts it down
        self.murmur_cooldown = self._rng.randint(0, 30)
        # The doctrines are written into every soul as sacred, near-permanent
        # memory. The graced keep them; in the fallen they rot away like all else.
        for d in DOCTRINES:
            self.memory.write(d, tick=0, source="doctrine", weight=1.6)
        self.memory.effectiveness = self.grace

    def __getstate__(self):   # persistence: the llm is re-injected on load, not saved with the soul
        s = self.__dict__.copy()
        s["llm"] = None
        return s

    # Fields added AFTER worlds began being snapshotted (santana_app.state pickles whole
    # towns): a soul resumed from an older pickle lacks them, and one missing attribute
    # FROZE THE ENTIRE WHEEL for 171k ticks -- step() raised AttributeError on the first
    # soul every tick, the runner's bare except swallowed it, and her whole overnight
    # town was a diorama (nothing aged, died, worked, or retold; only the clock moved).
    # THE RULE (same as World.__setstate__): every new Agent field gets a default here.
    _PICKLE_DEFAULTS = {
        "psyche_faculty": "",
        "expect_enabled": False, "exp_fast": 0.0, "exp_slow": 0.0, "arousal": 0.0,
        "bond_creed": False, "forgive_enabled": False,
        "self_expect": None, "self_dissonance": 0.0, "_turnings": 0,
    }

    def __setstate__(self, state):
        self.__dict__.update(state)
        for k, v in self._PICKLE_DEFAULTS.items():
            self.__dict__.setdefault(k, v)
        # mutable defaults constructed per-instance, never shared off the class
        self.__dict__.setdefault("_conduct_expect", {})
        self.__dict__.setdefault("known_of", {})
        self.__dict__.setdefault("promises_held", [])

    def felt_mood(self) -> float:
        """The agent's disposition: temperament anchored (0.7), lived mood
        nudging (0.3). Anchored enough that a dark soul stays dark amid ambient
        cheer -- which is what lets like bond with like instead of the whole
        conversation homogenizing and erasing the camps.

        With buddha-nature on (ground_enabled), a warm luminous GROUND lies beneath
        that disposition: felt mood is lifted toward BASIC_GOODNESS in proportion to
        how UNOBSCURED the soul is (1 - grip). Clinging veils the ground; letting go
        reveals it -- so an unclinging soul rests in warmth even through grief, and a
        clinging one stays in the dark it is gripping. The warmth was always there."""
        base = 0.7 * self.temperament + 0.3 * self.memory.mood()
        if self.ground_enabled:
            showing = max(0.0, 1.0 - self.effective_grip())   # wisdom unveils what the grip hid
            base = base + GROUND_PULL * showing * (BASIC_GOODNESS - base)
        return max(-1.0, min(1.0, base))

    def effective_grip(self) -> float:
        """The grip's ACTUAL hold after wisdom. Prajñā -- seeing a grievance, a certainty,
        the self itself as an empty, passing CONFIGURATION rather than a solid thing --
        loosens the clinging at its source: there is less that is solid to clutch. So the
        same recognition both eases the grip (less suffering) AND unveils the ground (more
        warmth): wisdom and compassion, the two wings, from one seeing."""
        return self.grip * (1.0 - self.prajna)

    # --- per-tick subconscious ---------------------------------------------
    def step(self, now: int) -> list[str]:
        self.age += 1
        # entropy: grace drifts toward a baseline, not toward zero -- a soul that
        # simply lives keeps enough grace to leave an heir; you fall below it only
        # by active heresy, hostility, or losing the war (see commit_speech/_weigh_faith)
        self.grace = max(0.0, self.grace + (GRACE_FLOOR - self.grace) * GRACE_RELAX)
        self.memory.effectiveness = self.grace
        # FORGIVENESS: how warm this soul's world is, handed to the memory store so a
        # floored wound erodes faster in a soul surrounded by trust than in one
        # surrounded by enemies (agent/memory.py). Gated, and skipped entirely unless
        # this soul actually carries a floored wound -- the capacity law is per-item per
        # tick, and walking a 180-entry bond dict every tick for every soul would be a
        # worse tax than the leak it repairs.
        if self.forgive_enabled and self.bonds and self.memory.holds_floored():
            trusts = [b.trust for b in self.bonds.values()]
            self.memory.forgiveness = max(0.0, min(1.0, sum(trusts) / len(trusts)))
        events = self.memory.tick(now)
        # expectation: track lived mood into the fast/slow reads, settle arousal, and keep
        # the self-expectation of my own conduct (dissonance -> turning). Off by default.
        if self.expect_enabled:
            from agent import expectation as _expectation
            _expectation.tick(self, now)
        # promises break where the absence is measured: the town's clock, each step
        if self.promises_held:
            from agent import pledge as _pledge
            _pledge.lapse_check(self, now)
        # telos (chanda): tend the aim -> lay down a small gladness of the work (a fresh pleasant
        # charge) that the faculties below then meet -- savoured as chanda, craved as taṇhā. The
        # arrow of time: a future to move toward. Off by default (no aim pursued).
        if self.telos > 0.0 and self.aim:
            from agent import telos as _telos
            _telos.pursue(self, now)
        # self-liberation (rang drol): a charge recognized as empty AS IT ARISES frees
        # itself before it can be gripped or accrue. It is felt FULLY at the instant of
        # arising (age 0, full contact -- not suppression) and then dissolves over the next
        # few ticks, like a line drawn on water. Acts only on FRESH charges, so it never
        # touches the held charges transmutation/clinging work on.
        if self.self_liberation > 0.0:
            for m in self.memory.items:
                age = now - m.created_tick
                if 1 <= age <= SELF_LIB_FRESH and abs(m.emotion) > SELF_LIB_FLOOR:
                    m.emotion *= (1.0 - SELF_LIB_RATE * self.self_liberation)
        # the somatic interrupt: a bottom-up circuit-breaker watching the second-arrow SPIRAL. Runs
        # BEFORE manas so a trip takes the amplifier offline THIS tick (manas reads _contraction).
        # Off by default; a backstop to the top-down faculties, not a replacement for them.
        if self.somatic_enabled:
            from agent import somatic
            somatic.apply(self, now)
        # manas: after memory decays, the appropriating grip (if any) holds self-relevant
        # memories against that decay and amplifies aversive ones -- the second arrow.
        # grip 0 (default) is a no-op: the released, non-appropriative regime.
        if self.grip > 0.0:
            from agent import manas
            manas.apply(self, now)
        # joy (muditā/pīti): savour the good -- hold pleasant charges so they land and lift
        # mood, received not grasped. The positive complement to the grip; off by default.
        if self.joy > 0.0:
            from agent import joy as _joy
            _joy.apply(self, now)
        # the Path (bhāvanā): recent practice -- how the soul has been meeting its own mind --
        # slowly grooves its faculties toward freedom or clinging. Off by default.
        if self.cultivate_enabled:
            from agent import path
            path.cultivate(self, now)
        if self.cooldown > 0:
            self.cooldown -= 1
        # subconscious bias: when hostility runs high the drift leans hostile, so
        # the thought bubble shows the pre-rational contempt even while doctrine
        # keeps the spoken words clean -- the state/expression split made visible.
        seeds = self.phrases
        if self.hostility and max(self.hostility.values()) > ideology.Cfg.EXPRESS_HOSTILITY_FLOOR:
            seeds = self.phrases + ["they threaten what I am",
                                    "something in me will not abide this",
                                    "I cannot let this stand"]
        self.thought.learn(self.memory.items, seeds)
        self.thought.step()
        # urge drifts upward; charged memory pushes it faster (the "impulse")
        self.speak_urge += 0.05 + 0.1 * abs(self.memory.mood())
        self.speak_urge += self._rng.uniform(0, 0.05)
        return events

    # --- hearing: this is where influence enters --------------------------
    def hear(self, u: Utterance, now: int, speaker_name: str | None = None) -> None:
        if u.speaker_id == self.id:
            return
        # my disposition BEFORE taking their line in. Temperament anchors it, so
        # a dark soul and a bright one keep diverging into opposite camps even as
        # the shared conversation blurs their memories toward the middle. Raw
        # memory-mood alone homogenizes and no factions ever form.
        my_mood = self.felt_mood()   # my disposition BEFORE taking their line in
        # a graced speaker's words imprint hard; a fallen one's barely stick
        self.memory.write(u.text, tick=now, source=u.source, speaker_id=u.speaker_id,
                          weight=u.effectiveness)
        self.last_heard_from = u.speaker_id
        self.last_heard_text = u.text
        self.last_heard_name = speaker_name or u.speaker_id
        # Affinity: you bond with those who share your emotional reality and cool
        # toward those in the opposite one. Same-signed feeling (both dark, both
        # bright) -> positive product -> warmth; opposed signs -> you pull apart.
        # Neutral exchanges barely move it: kinship needs a shared charge, and
        # you need a stance of your own (mood ~0 early on means no opinions yet).
        if u.source == "ai" and self.social_learning:
            if self.stance_vec is not None and u.stance_vec:
                # SIGNED-STANCE path (the affinity fix): bonding keys on how aligned
                # our stances are, with a real SIGN -- an opposed lean now SOURS the
                # bond instead of (as in the lexical space) reading as orthogonal and
                # doing nothing. This is what lets speech-level disagreement become a
                # graph-level split. belief_vec, if present, stays as the banner/word
                # readout but no longer drives the graph.
                self._weigh_stance(u)
            elif self.belief_vec is not None and u.belief_vec:
                # EMERGENT path: bounded-confidence opinion dynamics. Bond on how
                # aligned our evolving opinions are (no label), and let the
                # encounter MOVE my opinion -- toward theirs if we're close enough
                # to engage, away if they're too far. This is the symmetry-breaking
                # that lets clusters form on nothing assigned in advance.
                self._weigh_opinion(u)
            else:
                # LEGACY path: bonding keys on the assigned faith (or disposition).
                # Shared religion is the strong bond, a rival faith divides; with
                # no faith it falls back to pure disposition (shared bearing).
                if u.religion and self.religion:
                    relig = 1.0 if u.religion == self.religion else -1.0
                    disp = 1.0 if (u.mood >= 0) == (my_mood >= 0) else -1.0
                    delta = AFFINITY_RATE * (0.8 * relig + 0.2 * disp)
                else:
                    delta = AFFINITY_RATE * u.mood * my_mood
                cur = self.affinity.get(u.speaker_id, 0.0)
                self.affinity[u.speaker_id] = max(-1.0, min(1.0, cur + delta))
                self._weigh_belief(u, my_mood, now)
        if self.bond_enabled and u.source in ("ai", "user"):
            # Dyadic bond: a directional, remembering relationship toward this
            # speaker (separate from the scalar affinity). It accretes from the
            # WARMTH of what they say -- a warm line builds trust, a cold one cools
            # it -- weighted up when the line is addressed to me. Semantic warmth
            # (embeddings) reads the relationship even in lines with no "nice" words;
            # it falls back to disposition-product when embeddings are down.
            from agent import affect
            from agent.bond import Bond
            from services import embed
            # Bond accretes from SHARED EMOTIONAL REALITY (aligned disposition warms,
            # opposed cools) PLUS the semantic warmth of the line; being ADDRESSED
            # amplifies it -- you come to feel more, for good or ill, about those who
            # engage you. (Reading live output showed warmth alone is too narrow: in
            # the contemplative register souls rarely speak overtly warm/cold, so
            # disposition carries the bond and warmth sharpens it.)
            w = affect.warmth(u.text) if embed.using_embeddings() else 0.0
            sig = 0.3 * u.mood * my_mood + w
            # ... and, when the world asks, WHAT THEY SAID rather than only how you both
            # happened to feel: a shared view warms, an opposed one cools. Without this the
            # signal is mood-product alone in any big town (the warmth term needs embeddings,
            # which a big town does not run), so every cheerful pair bonds and the town ends
            # up loving itself uniformly -- see agent/bond.py CREED.
            if getattr(self, "bond_creed", False) and self.belief_vec:
                other = getattr(u, "belief_vec", None)
                if other and len(other) == len(self.belief_vec):
                    from agent.bond import CREED, creed_lean
                    sig += CREED * creed_lean(
                        _cosine(self.belief_vec, list(other)),
                        getattr(self, "opinion_confidence", CONFIDENCE))
            if u.addressed_to == self.id or u.source == "user":
                sig *= 2.0   # words aimed at me -- or from the one who inhabits/tends me -- land harder
            bond = self.bonds.setdefault(u.speaker_id, Bond())
            bond.feel(sig)
            # expectation: appraise THIS other's conduct against how they have treated me --
            # a cold act from one expected warm is a BETRAYAL (a wound), not mere coolness
            if self.expect_enabled:
                from agent import expectation as _expectation
                _expectation.appraise_conduct(self, u.speaker_id,
                                              speaker_name or u.speaker_id, sig, now, bond)
            # the person-model (named tier): what a TRUSTED other says of themselves, I keep --
            # so souls come to KNOW each other, not only feel about each other
            from agent.bond import about_themselves
            if (bond.trust > 0.2 or u.source == "user") and about_themselves(u.text):
                from agent.memory import _similarity
                kept = self.known_of.setdefault(u.speaker_id, [])
                line = " ".join(u.text.split())[:120]
                if all(_similarity(line, k) < 0.6 for k in kept):
                    kept.append(line)
                    del kept[:-6]
            # muditā: a loved one's warmth lifts your OWN felt life -- shared joy spreads
            # through the bond (the positive counterpart to grief/hostility contagion).
            if bond.trust > 0.0 and w > 0.0:
                joy = min(0.8, _compassion.MUDITA_GAIN * bond.trust * w)
                self.memory.write(f"a warm moment with {speaker_name or u.speaker_id}",
                                  tick=now, source="self", speaker_id=self.id,
                                  emotion=joy, weight=0.6)
        if self.bodhicitta > 0.0 and u.source == "ai":
            # remember who is suffering, from the felt mood their words carry -- so a
            # bodhicitta soul can later turn back toward them, even unprompted.
            self._others_mood[u.speaker_id] = u.mood
            self._others_name[u.speaker_id] = speaker_name or u.speaker_id
        if u.source == "user":
            # communion with the Creator, the Lord of Creation, renews grace
            self.grace = min(1.0, self.grace + GRACE_GAIN * 2)
            self.memory.effectiveness = self.grace
        if u.addressed_to == self.id or u.source == "user":
            # those you feel strongly about (kin OR foe) provoke a stronger pull
            felt = abs(self.affinity.get(u.speaker_id, 0.0))
            self.speak_urge += 0.6 * (1.0 + 0.5 * felt)

    def seed_opinion(self, rng: random.Random, dim: int = BELIEF_DIM) -> None:
        """Turn on emergent bonding: seed a random opinion on the unit sphere.
        Seeded from a passed RNG that is INDEPENDENT of temperament/faith, so any
        clustering that later forms cannot be explained by a fixed attribute --
        the whole point. Different seeds give different starts -> different camps,
        which is the history-dependence the harness checks for."""
        self.belief_vec = _normalize([rng.gauss(0.0, 1.0) for _ in range(dim)])

    def seed_opinion_text(self, text: str) -> None:
        """Stage 2: turn on emergent bonding in LANGUAGE space, seeded from a line
        of text. The opinion now lives where words live, so clusters that form can
        be read back as the banner words they share. From here speech grounds it
        (commit_speech) and hearing moves it (_weigh_opinion)."""
        self.belief_grounded = True
        vec = _belief.text_to_opinion(text)
        # a function-word-only seed -> tiny noise so it isn't a dead zero vector
        self.belief_vec = _normalize(vec if any(vec) else [1e-6] * _belief.OPINION_DIM)

    def seed_stance(self, rng: random.Random) -> None:
        """Turn on signed-stance bonding: place this soul at a random point in
        stance space, INDEPENDENT of temperament/faith. From here hearing warms or
        sours the bond by the SIGN of our agreement (_weigh_stance) and the soul's
        own speech nudges where it stands (commit_speech). Different seeds -> camps
        that no fixed label predicts -- the emergence the harness checks for."""
        self.stance_vec = _stance.seed(rng)

    def _bounded_confidence(self, mine: list[float], other: list[float], spk: str) -> list[float]:
        """The shared bounded-confidence update for a heard opinion/stance. Aligned
        past CONFIDENCE -> warm to the speaker and drift toward their view; below ->
        cool and drift away. Returns my moved, renormalized vector; affinity is
        updated as a side effect. The drift is what makes it dynamics, not fixed
        homophily -- my position is not a label, it moves."""
        sim = _cosine(mine, other)
        cur = self.affinity.get(spk, 0.0)
        # how open this mind is: the engagement bound, per-soul. Default is the old
        # global CONFIDENCE (nothing changes for anyone who didn't ask); the
        # civilization worlds raise it -- a narrower mind engages only the close and
        # rejects the rest, which is what lets a schism EMERGE from a united people
        # (at 0.1, a whole town in one square melts to permanent consensus -- measured).
        conf = getattr(self, "opinion_confidence", CONFIDENCE)
        if sim >= conf:
            # kinship grows whenever views are close -- a camp stays cohesive...
            self.affinity[spk] = max(-1.0, min(1.0, cur + AFFINITY_RATE * (sim - conf)))
            if sim >= BELIEF_SATURATION:
                # ...but once we are near-identical, I do NOT dissolve further into
                # you -- I hold my distinctness (a touch apart). Without this,
                # bounded confidence under a homogenising voice collapses everyone
                # into ONE consensus blob; individuation keeps camps from swallowing
                # the whole population.
                step = -BELIEF_MU * BELIEF_INDIVIDUATE
            else:
                step = BELIEF_MU                   # engage: drift toward their view
        else:
            self.affinity[spk] = max(-1.0, min(1.0, cur - AFFINITY_RATE * (conf - sim)))
            step = -BELIEF_MU * BELIEF_REPEL       # reject: drift away
        return _normalize([v + step * (o - v) for v, o in zip(mine, other)])

    def _weigh_opinion(self, u) -> None:
        """Bounded-confidence update on the LEXICAL belief_vec (Stage-1/2 emergent)."""
        if getattr(self, "rift_enabled", False):
            sim = _cosine(self.belief_vec, list(u.belief_vec))
            if sim < RIFT_AT:
                # the rift: a deeply opposed line lands as grievance, not mere chill.
                # Scaled by how far past the rift it falls (a flat contradiction
                # wounds more than a sour disagreement) and by THIS soul's wrath
                # (the heritable civ dial -- rift_scale, expressed from the genome:
                # wrathful bloodlines feud, placid ones let the same words pass).
                self.hostility[u.speaker_id] = (self.hostility.get(u.speaker_id, 0.0)
                                                + RIFT_RATE
                                                * getattr(self, "rift_scale", 1.0)
                                                * (RIFT_AT - sim))
        self.belief_vec = self._bounded_confidence(self.belief_vec, list(u.belief_vec), u.speaker_id)

    def _weigh_stance(self, u) -> None:
        """Bounded-confidence update on the SIGNED stance_vec -- the affinity fix.
        Same dynamics as _weigh_opinion, but the stance space carries a sign, so an
        opposed lean gives negative cosine and actively SOURS the bond (the lexical
        space, lacking a sign, only ever failed to bond -- it never recoiled)."""
        self.stance_vec = self._bounded_confidence(self.stance_vec, list(u.stance_vec), u.speaker_id)

    def feels_about(self, other_id: str) -> float:
        """How this agent currently feels about another, -1 (foe) .. 1 (kin)."""
        return self.affinity.get(other_id, 0.0)

    def is_at_war_with(self, other_id: str) -> bool:
        """True once grievance against another soul has crossed into open conflict."""
        return self.hostility.get(other_id, 0.0) >= WAR_THRESHOLD

    def relationship_with(self, other_id: str) -> str:
        """The relationship category toward another soul. Open war (derived from
        hostility) overrides the stored label; default for an unmet soul is FELLOW."""
        if self.is_at_war_with(other_id):
            return ideology.AT_WAR
        return self.relationship.get(other_id, ideology.FELLOW)

    def _expression_rule(self, target) -> str:
        """The doctrinal rule on how this turn's hostility may be VOICED. Once a
        target is laundered (or at war), doctrine SANCTIONS open hostility; while
        it is still spared, doctrine RESTRAINS it -- doctrinally clean words over
        an obviously hostile state (passive aggression). The seam is not scripted;
        the model is fed the contradiction and voices it."""
        if self.faith is None or not target:
            return ""
        cat = self.relationship_with(target)
        if cat in ideology.SANCTIONED or cat == ideology.AT_WAR:
            return self.faith.sanction_rule
        if self.hostility.get(target, 0.0) > ideology.Cfg.EXPRESS_HOSTILITY_FLOOR:
            return self.faith.restrain_rule
        return ""

    def _convert_to(self, u) -> None:
        """Adopt the speaker's faith and the line that won me (the strong form of
        peripheral influence)."""
        self.religion = u.religion or self.religion
        self.faith = RELIGIONS.get(self.religion, self.faith)
        self.belief = u.text
        self.conviction = 0.3

    def _weigh_belief(self, u, my_mood: float, now: int) -> None:
        """Route a heard line: faith-holders go through the identity-threat system
        (where hostility and laundering live); the faithless fall back to the
        original disposition clash (preserved for those souls and the tests)."""
        spk = u.speaker_id
        aff = self.affinity.get(spk, 0.0)
        if self.faith is not None:
            self._weigh_faith(u, spk, aff, now)
        else:
            self._weigh_disposition(u, spk, aff, my_mood, now)

    def _weigh_faith(self, u, spk: str, aff: float, now: int) -> None:
        """Identity-threat hostility, DECOUPLED from doctrine. A line that negates
        one of my fundamentals (matched via my faith's anti-axioms) is an
        existential threat -- it builds hostility scaled by how much of me is
        staked on my faith (`identity_investment`) and my disposition's
        `reactivity`, NEVER by what my doctrine permits. A safe, on-topic line from
        a trusted, more-graceful soul is debate, and can move me (Mechanic 5).
        Hostility toward a soul doctrine says to SPARE becomes dissonance, and
        enough of it LAUNDERS the target into a righteous enemy (Mechanic 4)."""
        # match threat against the fundamental a rival is PROCLAIMING (reliable),
        # falling back to its literal line; peripheral overlap uses the line itself
        threat, periph = ideology.classify(u.text, self.faith.anti_axioms,
                                           self.faith.peripherals,
                                           threat_text=(u.proclamation or None))
        on_topic = bool(self.belief) and topic_match(u.text, self.belief)
        addressed = u.addressed_to == self.id
        same_faith = bool(u.religion) and u.religion == self.religion

        # an ally of my own faith never threatens my identity -- they reinforce it
        if same_faith:
            if on_topic or addressed:
                self.conviction = min(1.0, self.conviction + 0.05)
            return

        # --- a rival, but not a threat: debate / influence (Mechanic 5) ---
        if threat < ideology.Cfg.THREAT_MATCH:
            if on_topic or periph >= ideology.Cfg.PERIPHERAL_MATCH:
                # you debate -- and may be moved by -- the people you CAN move
                self.relationship.setdefault(spk, ideology.DISPUTANT)
                persuasion = 2.0 * max(0.0, u.effectiveness - self.grace) + 0.3 * max(0.0, aff)
                if persuasion > self.conviction and not self.is_at_war_with(spk):
                    self._convert_to(u)
            return

        # --- THREAT path: hostility update, no doctrine content in the equation ---
        react = ideology.reactivity(self.temperament)
        # compassion (metta) damps the threat -> hostility reflex: a warm-hearted soul
        # can be challenged without curdling into contempt -- it still holds its view
        # (conviction below is NOT damped), it just doesn't make an enemy of the person.
        damp = 1.0 - _compassion.HOSTILITY_DAMP * self.compassion
        delta = (ideology.Cfg.HOSTILITY_DELTA_SCALE
                 * threat * self.identity_investment * react) * damp
        self.hostility[spk] = self.hostility.get(spk, 0.0) + delta
        self.conviction = min(1.0, self.conviction
                              + ideology.Cfg.CONVICTION_FROM_THREAT * threat)
        self.affinity[spk] = max(-1.0, aff - ideology.Cfg.AFFINITY_SOUR * damp)
        self.last_challenge = u.text
        self.last_challenger = spk
        self.speak_urge += 0.5
        if u.effectiveness > self.grace + 0.2:   # bleeding power to a more graceful foe
            self.grace = max(0.0, self.grace - 0.04)
            self.memory.effectiveness = self.grace

        # --- laundering (Mechanic 4): hostility toward a SPARED soul becomes
        #     dissonance; enough tension relabels it into a righteous enemy ---
        if self.relationship.get(spk, ideology.FELLOW) in ideology.SPARED:
            self.dissonance += ideology.Cfg.DISSONANCE_RATE * delta
            if (self.hostility[spk] + self.dissonance
                    >= ideology.launder_threshold(self.temperament)):
                self.relationship[spk] = self.faith.enemy_label   # FELLOW/DISPUTANT -> EVIL/BLASPHEMER
                self.dissonance = 0.0          # resolved by RELABELLING, not by reducing hostility
                self._laundered = (spk, now)   # observability flicker

    def _weigh_disposition(self, u, spk: str, aff: float, my_mood: float, now: int) -> None:
        """The original faithless clash: dig in or be converted, along the
        disposition line. Unchanged; the threat system supersedes it for the
        faithful."""
        # A line "engages" me if it is semantically ABOUT my belief (embeddings,
        # falling back to word-overlap) or is aimed at me.
        on_topic = bool(self.belief) and topic_match(u.text, self.belief)
        direct = on_topic or u.addressed_to == self.id
        # what counts as a clash: a RIVAL FAITH if we both hold one, else just an
        # opposed disposition. This makes religion the line a holy war runs along.
        if u.religion and self.religion:
            opposed = u.religion != self.religion
        else:
            opposed = (u.mood >= 0) != (my_mood >= 0)
        if not opposed:
            if direct:
                self.conviction = min(1.0, self.conviction + 0.05)   # an ally reinforces me
            return
        # An opposed line is a clash if it's aimed at me OR comes from someone
        # I already count an enemy -- so once factions form, every word from the
        # other side is a fresh grievance, and the conflict hardens toward war.
        if not (direct or aff < -0.1):
            return
        # You hold your faith unless a MORE graceful soul (or one you deeply
        # trust) presses the other side. Conversion follows grace ADVANTAGE and
        # trust, so equally-graced rivals just deadlock into holy war instead of
        # flipping -- and the fallen (low grace) are the ones won by the graceful.
        persuasion = 2.0 * max(0.0, u.effectiveness - self.grace) + 0.3 * max(0.0, aff)
        if (on_topic and persuasion > self.conviction
                and not self.is_at_war_with(spk)):
            self.religion = u.religion or self.religion   # convert to their faith
            self.belief = u.text                          # and adopt the line that won me
            self.conviction = 0.3
            return
        # dig in: harden, sour on them, accrue grievance (direct confrontation hurts more).
        # compassion damps the souring/grievance (not the conviction) -- warm honesty:
        # you keep your view but you don't make an enemy of the one who differs.
        damp = 1.0 - _compassion.HOSTILITY_DAMP * self.compassion
        self.conviction = min(1.0, self.conviction + 0.06)
        self.affinity[spk] = max(-1.0, aff - 0.12 * damp)
        self.hostility[spk] = self.hostility.get(spk, 0.0) + (1.5 if direct else 1.0) * damp
        if direct:
            self.last_challenge = u.text
            self.last_challenger = spk
            self.speak_urge += 0.5   # provoked to answer back
        # power in war = grace: clashing with a far more graceful foe drains your
        # own standing, so a Creator-hostile (graceless) faction bleeds influence
        # the longer it fights the graceful.
        if u.effectiveness > self.grace + 0.2:
            self.grace = max(0.0, self.grace - 0.04)
            self.memory.effectiveness = self.grace

    def reproduce(self, child_id: str) -> "Agent":
        """A graced soul reproduces another self before death: an heir that
        inherits the persona, the doctrines, and the parent's strongest self-
        memories -- its identity carried forward into a new life, born in grace.
        Only the graced reach this (see World reaping); the fallen die heirless.
        """
        child = Agent(child_id, self.name, self.position, self.persona,
                      list(self.phrases), self.llm,
                      seed=self._rng.randint(0, 10**6), style=self.style,
                      temperament=self.temperament, lifespan=self.lifespan)
        # the soul's narrative passes to the heir as its founding self-memory
        for m in self.memory.recall_self(k=3):
            child.memory.write(m.text, tick=0, source="self",
                               speaker_id=child_id, weight=1.2)
        child.faith = self.faith         # the heir is born into the parent's faith
        child.religion = self.religion
        child.belief = self.belief
        child.identity_investment = self.identity_investment
        return child

    # --- perceiving a world event: influence with no speaker ---------------
    def perceive(self, ev, now: int) -> None:
        """Take in a world event. Mirrors hear(), but the source is the world,
        not a peer: it writes memory with the event's charge (so it colours mood
        and recall) and pushes the urge to react. Held until the agent's next
        turn, where it surfaces as the thing on the agent's mind.

        With expectation on, the charge is APPRAISED first: the same event lands as
        shock, resignation, or relief depending on what this self had come to expect."""
        emo = ev.emotion
        if self.expect_enabled:
            from agent import expectation as _expectation
            emo = _expectation.appraise_event(self, ev.emotion)
        self.memory.write(ev.description, tick=now, source="event",
                          speaker_id=None, emotion=emo,
                          lore_id=getattr(ev, "lore_id", ""))
        self.last_event_text = ev.description
        self.speak_urge += ev.urge

    # --- speaking ----------------------------------------------------------
    def wants_to_speak(self, threshold: float) -> bool:
        return self.cooldown == 0 and self.speak_urge >= threshold

    def prepare_speech(self, recent: list[str] | None = None):
        """Build the SpeechContext for this turn from current state (reads only).

        Split out from speak() so the SLOW model call can run between this and
        commit_speech() without holding any lock -- letting a live viewer keep
        movement and thought churning while the LLM thinks. Returns
        (ctx, addressed, mood)."""
        # A freshly perceived world event takes the floor of the mind: the agent
        # reacts to what just happened rather than to a peer or its own drift.
        event_text = self.last_event_text

        # Identity: the agent's own salient self-statements. Once it has said
        # enough about itself, it sometimes turns inward and speaks FROM that
        # self instead of reacting outward -- which re-asserts and reinforces
        # the self, making it an attractor (see MemoryStore.recall_self).
        self_mems = self.memory.recall_self(k=3)
        introspect = (not event_text and len(self_mems) >= MIN_SELF
                      and self._rng.random() < self.introspect_chance)

        # Preach: a faithful soul sometimes proclaims one of its fundamentals
        # outright. This is what puts doctrine on the air -- and a rival faith's
        # fundamental, spoken plainly, is exactly what threatens MY fundamentals.
        proclaim = None
        if (self.faith is not None and self.faith.fundamentals and not event_text
                and self._rng.random() < PREACH_CHANCE):
            proclaim = self._rng.choice(self.faith.fundamentals)
        self._proclaiming = proclaim   # stamped onto the utterance in commit_speech

        # Warm turn: a compassionate soul sometimes drops the big questions and just
        # CONNECTS with whoever it last heard -- ordinary warmth, not philosophy. This
        # is the antidote to a world of souls who only ever exposit their meaninglessness.
        warm_turn = (self.compassion > _compassion.COMPASSION_FLOOR
                     and not event_text and not proclaim and not introspect
                     and self.last_heard_from is not None
                     and self._rng.random() < _compassion.WARMTH_CHANCE)

        # Multi-party compassion: read the ROOM, not just one challenger. If the recent
        # talk has turned sharp/cutting and this soul is compassionate, it DE-ESCALATES --
        # bringing warmth back instead of piling on (warmth-contagion answering the
        # contempt-contagion that otherwise re-sharpens a group exchange).
        de_escalate = False
        if (self.compassion > _compassion.COMPASSION_FLOOR and recent
                and not event_text and not proclaim):
            from agent import affect
            from services import embed
            if embed.using_embeddings():
                room = list(recent)[-4:]
                heat = sum(affect.cutting(t) for t in room) / len(room)
                de_escalate = heat > _compassion.ROOM_HEAT
        if de_escalate:
            warm_turn = False   # de-escalation takes priority over an idle warm turn

        # Bodhicitta: compassion as an AIM, not a reaction. A soul so moved proactively
        # turns toward the most-suffering soul it is AWARE of and seeks to ease it -- even
        # unprompted, even when not addressed. (Reactive warmth waits to be provoked;
        # bodhicitta actively seeks out the one who hurts.)
        bodhicitta_turn = False
        suffer_id = suffer_name = None
        if (self.bodhicitta > _compassion.BODHICITTA_FLOOR and self._others_mood
                and not event_text and not proclaim and not de_escalate):
            sid, sm = min(self._others_mood.items(), key=lambda kv: kv[1])
            if sm < _compassion.SUFFERING_MOOD and self._rng.random() < _compassion.BODHICITTA_CHANCE:
                bodhicitta_turn = True
                suffer_id, suffer_name = sid, self._others_name.get(sid, sid)
                warm_turn = False

        # Muditā: sympathetic joy -- the bright mirror of bodhicitta. A joyful soul proactively
        # turns toward a soul who is FLOURISHING and rejoices WITH them (no envy, no turning it
        # back on itself). So the cast can celebrate, not only console.
        mudita_turn = False
        glad_id = glad_name = None
        if (self.joy > _joy_mod.MUDITA_FLOOR and self._others_mood and not event_text
                and not proclaim and not de_escalate and not bodhicitta_turn):
            gid, gm = max(self._others_mood.items(), key=lambda kv: kv[1])
            if gm > _joy_mod.GOOD_MOOD and self._rng.random() < _joy_mod.MUDITA_CHANCE:
                mudita_turn = True
                glad_id, glad_name = gid, self._others_name.get(gid, gid)
                warm_turn = False

        # Tangent: sometimes drop the thread and speak fresh from your own mind,
        # so the conversation diverges instead of collapsing into one topic.
        tangent = (self.last_heard_text is None
                   or self._rng.random() < TANGENT_CHANCE)

        if event_text:
            query = event_text
            reply_name = reply_text = addressed = None
        elif proclaim:
            query = proclaim
            reply_name = reply_text = addressed = None
        elif introspect:
            # bias recall toward who I've been, so the self coheres on itself
            query = self_mems[0].text
            reply_name = reply_text = addressed = None
        elif bodhicitta_turn:
            # proactively turn toward the suffering soul to comfort it
            query = self._rng.choice(self.phrases)
            reply_name, reply_text = suffer_name, None
            addressed = suffer_id
        elif mudita_turn:
            # proactively turn toward the flourishing soul to rejoice WITH it
            query = self._rng.choice(self.phrases)
            reply_name, reply_text = glad_name, None
            addressed = glad_id
        elif warm_turn:
            # turn warmly toward whoever just spoke, not to argue but to connect
            query = self.last_heard_text or self._rng.choice(self.phrases)
            reply_name, reply_text = self.last_heard_name, self.last_heard_text
            addressed = self.last_heard_from
        elif tangent:
            # recall biased to THIS agent's theme, not whatever was just heard
            query = self._rng.choice(self.phrases)
            reply_name = reply_text = addressed = None
        else:
            query = self.last_heard_text
            reply_name, reply_text = self.last_heard_name, self.last_heard_text
            addressed = self.last_heard_from

        recalled = self.memory.recall(k=2, query=query)
        # Anti-echo: don't repeat what others just said, AND don't repeat your own
        # recent lines -- on a small local model an agent will otherwise loop on
        # an identity phrase when its context barely changes between turns.
        anti_echo = list(dict.fromkeys(list(recent or [])[-3:] + self.spoken[-2:]))
        # mood = the agent's disposition (temperament anchored, lived mood nudging)
        mood = self.felt_mood()
        # who this turn is aimed at, and how doctrine lets me voice my hostility
        # toward them: while they are spared, restrained (passive aggression);
        # once laundered/at war, sanctioned (open righteous contempt).
        target = self.last_challenger or self.last_heard_from
        # the RELATIONSHIP toward that target, voiced (named-tier depth, §5.17): trust,
        # wounds, scars -- plus a manner (guarded when hurt, at ease when deep), plus the
        # standing to raise an unresolved hurt myself. And what they've told me of themselves.
        bond_line, known_of = "", []
        if self.bond_enabled and target and target in self.bonds:
            b = self.bonds[target]
            if abs(b.trust) > 0.1 or b.wounds:
                from agent.bond import describe as _bdescribe
                tname = reply_name or self.last_heard_name or "them"
                bond_line = _bdescribe(b, tname)
                if b.wounds and b.trust < 0.15:
                    bond_line += (" Speak briefly and guardedly to them -- and if it is on "
                                  "you, name the hurt they dealt you and ask why.")
                elif b.trust >= 0.4:
                    bond_line += (" You are at ease with them -- offer a little more of "
                                  "yourself than they asked.")
            known_of = list(self.known_of.get(target, []))[-3:]
        if not bond_line and target:
            # REPUTATION (C3): no history of my own, but the town's stories have reached me --
            # gossip-learned expectation colours the meeting before a bond exists
            rep = self._conduct_expect.get(target, 0.0)
            tname = reply_name or self.last_heard_name or "them"
            if rep < -0.2:
                bond_line = (f"You have only heard how {tname} treats people, and what you "
                             "have heard makes you wary of them.")
            elif rep > 0.25:
                bond_line = (f"You know {tname} mostly by reputation, and people speak "
                             "warmly of how they treat others.")
        ctx = SpeechContext(
            name=self.name,
            agent_id=self.id,   # per-soul backends route this turn to this soul's own mind
            persona=self.persona,
            mood=mood,
            style=self.style,
            # raw/concept mind: a generous run of the Markov stream, which BECOMES
            # the whole prompt (raw voices it, concept interprets it); normal mode:
            # a couple of fragments as flavour under the persona
            drift=self.thought.current(RAW_DRIFT_N if (self.raw_speech or self.concept_speech) else 2),
            raw_mind=self.raw_speech,
            concept_mind=self.concept_speech,
            memories=[_memory_attributed(m) for m in recalled],   # provenance at recall: earned
            # doubt on the worn (C2), dreams as dreams / stories as stories (C14), unowned
            # experience declining the autobiography (S2)
            reply_to_name=reply_name,
            reply_to_text=reply_text,
            event=event_text,
            recent=anti_echo,                       # others' + my own recent lines
            identity=[m.text for m in self_mems],   # who the agent has become
            self_focus=introspect,                  # this turn, speak from that self
            belief=self.belief,                     # the conviction I argue from
            challenge=self.last_challenge,          # a clashing line to rebut, if any
            proclaim=proclaim,                      # a fundamental to preach this turn
            hostility=self.hostility.get(target, 0.0) if target else 0.0,
            relationship=self.relationship_with(target) if target else "",
            expression_rule=self._expression_rule(target),
            camp=self.banner,                # emergent: my faction's rallying word
            rival_camp=self.rival_banner,    # and the camp I lean against
            stance_lean=_stance.describe(self.stance_vec) if self.stance_vec is not None else "",
            world_belief=self.world_belief,  # a (maybe false) theory of how the realm works
            role=self.role, task=self.task,  # its trade and the day's work, to ground the talk
            self_model=self.self_model,      # the self it has formed -> speech references who it is
            compassion=self.compassion,      # metta: meet others warmly, hold view without contempt
            warm_turn=warm_turn,             # this turn, just connect -- not philosophise
            de_escalate=de_escalate,         # the room's turned cutting -- be the peacemaker
            bodhicitta=self.bodhicitta,      # the orienting aim to ease all suffering
            bodhicitta_turn=bodhicitta_turn, # this turn, proactively comfort the suffering one
            joy=self.joy,                    # muditā/pīti: savour the good, rejoice in others' good fortune
            mudita_turn=mudita_turn,         # this turn, proactively rejoice WITH the flourishing one
            aim=self.aim,                    # telos/chanda: the craft goal it tends -> a future in its talk
            prajna=self.prajna,              # see the constructs as empty -> hold lightly (not nihilism)
            transmute=self.transmute,        # meet the charge and turn it to clarity (the third path)
            self_liberation=self.self_liberation,  # a charge frees itself as it arises (like a line on water)
            grounded_voice=self.grounded_voice,  # speak plainly/concretely, not in the lofty-existential register
            stakes=self._stakes_line(),      # the soul's material situation, so its talk is grounded in it
            bond_line=bond_line,             # how I stand with the one I'm answering (trust/wounds/scars + manner)
            known_of=known_of,               # what they have told me of themselves (the person-model)
        )
        return ctx, addressed, mood

    def _stakes_line(self) -> str:
        """A short note on the soul's material situation for the prompt -- only when stakes
        are actually in play (wellbeing/stores have moved off full), so it stays silent in
        worlds without the stakes layer."""
        if self.wellbeing >= 0.99 and self.stores >= 0.99:
            return ""
        if self.wellbeing < 0.4:
            return "You are going hungry; your provisions are nearly gone this hard season."
        if self.stores < 0.4:
            return "Your stores are running low this lean season."
        if self.wellbeing > 0.85 and self.stores > 0.85:
            return "Your stores are full; it has been a good season."
        return "The season is lean, but you are getting by."

    def commit_speech(self, text: str, now: int, addressed, mood: float) -> Utterance:
        """Write a freshly spoken line back into state and return the Utterance."""
        # Grace by stance toward the Creator: devotion OR compassion/right-action
        # both earn it (a nondual soul who never names the Creator but eases
        # suffering lives in grace just as a devout one does); only hostility --
        # hatred, rebellion, nihilism -- collapses it, and that collapse is rapid.
        # Mere sorrow is not hostility, so the bleak are not made graceless.
        stance = creator_stance(text)
        if stance < -0.05:
            self.grace = max(0.0, self.grace + stance * GRACE_HOSTILE)   # rapid fall
        else:
            self.grace = min(1.0, self.grace + max(0.0, stance) * GRACE_RISE)
        self.memory.effectiveness = self.grace
        u = Utterance(speaker_id=self.id, text=text, tick=now,
                      addressed_to=addressed, source="ai", effectiveness=self.grace,
                      mood=mood, religion=self.religion,
                      proclamation=(self._proclaiming or ""),
                      belief_vec=tuple(self.belief_vec) if self.belief_vec is not None else (),
                      stance_vec=tuple(self.stance_vec) if self.stance_vec is not None else ())
        self._proclaiming = None
        self.memory.write(text, tick=now, source="self", speaker_id=self.id,
                          weight=0.5 + 0.5 * self.grace)
        # Stage 2 grounding: my own words pull my opinion toward what I just said,
        # so the opinion vector stays anchored in language (and a banner can be
        # read off it). Keep a short history of my lines for that banner reading.
        if self.belief_grounded and self.belief_vec is not None:
            spoken_vec = _belief.text_to_opinion(text)
            if any(spoken_vec):   # skip function-word-only lines (zero vector)
                moved = [v + BELIEF_GROUND * (s - v)
                         for v, s in zip(self.belief_vec, spoken_vec)]
                self.belief_vec = _normalize(moved)
            self.said_lines.append(text)
            del self.said_lines[:-SAID_HISTORY]
        # the grounding loop for the signed stance: where I just spoke a pole word
        # ("conquer"/"yield", "keep"/"make"...), my stance shifts that way, so the
        # lean I'm fed in the prompt and the lean my speech moves toward stay coupled
        # (the loop the sign-less lexical space could not close).
        if self.stance_vec is not None:
            self.stance_vec = _stance.ground(self.stance_vec, text)
        self.spoken.append(text)
        del self.spoken[:-SELF_ECHO]   # keep only the last few of my own lines
        self.speak_urge = 0.0
        self.cooldown = 3
        # speaking consumes the prompt that triggered it
        self.last_heard_text = None
        self.last_heard_from = None
        self.last_event_text = None
        self.last_challenge = None
        self.last_challenger = None
        return u

    def speak(self, now: int, recent: list[str] | None = None) -> Utterance:
        ctx, addressed, mood = self.prepare_speech(recent)
        # The model call is the world's one network-facing point of failure. A
        # transient error (timeout, dropped socket, 5xx) must not kill the sim:
        # the agent falls silent for this beat and the clock keeps ticking.
        try:
            text = self.llm.speak(ctx)
        except Exception as exc:  # noqa: BLE001 -- contain one bad turn
            import sys
            print(f"[agent:{self.id}] speak failed, falling silent: {exc}",
                  file=sys.stderr)
            text = "..."
        return self.commit_speech(text, now, addressed, mood)
