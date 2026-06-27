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
from agent import ideology
from agent.doctrine import DOCTRINES, creator_stance
from agent.memory import MemoryStore
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
        self.bonds: dict = {}                # directional bonds toward other selves (see agent/bond.py)
        self.grip = 0.0                      # Stage-4 manas: appropriation strength [0,1]; 0 = released (default)
        self.compassion = 0.0                # Stage-6 metta/karuṇā: warm engagement [0,1]; 0 = off (default)
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

    def felt_mood(self) -> float:
        """The agent's disposition: temperament anchored (0.7), lived mood
        nudging (0.3). Anchored enough that a dark soul stays dark amid ambient
        cheer -- which is what lets like bond with like instead of the whole
        conversation homogenizing and erasing the camps."""
        return max(-1.0, min(1.0, 0.7 * self.temperament + 0.3 * self.memory.mood()))

    # --- per-tick subconscious ---------------------------------------------
    def step(self, now: int) -> list[str]:
        self.age += 1
        # entropy: grace drifts toward a baseline, not toward zero -- a soul that
        # simply lives keeps enough grace to leave an heir; you fall below it only
        # by active heresy, hostility, or losing the war (see commit_speech/_weigh_faith)
        self.grace = max(0.0, self.grace + (GRACE_FLOOR - self.grace) * GRACE_RELAX)
        self.memory.effectiveness = self.grace
        events = self.memory.tick(now)
        # manas: after memory decays, the appropriating grip (if any) holds self-relevant
        # memories against that decay and amplifies aversive ones -- the second arrow.
        # grip 0 (default) is a no-op: the released, non-appropriative regime.
        if self.grip > 0.0:
            from agent import manas
            manas.apply(self, now)
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
            if u.addressed_to == self.id or u.source == "user":
                sig *= 2.0   # words aimed at me -- or from the one who inhabits/tends me -- land harder
            bond = self.bonds.setdefault(u.speaker_id, Bond())
            bond.feel(sig)
            # muditā: a loved one's warmth lifts your OWN felt life -- shared joy spreads
            # through the bond (the positive counterpart to grief/hostility contagion).
            if bond.trust > 0.0 and w > 0.0:
                joy = min(0.8, _compassion.MUDITA_GAIN * bond.trust * w)
                self.memory.write(f"a warm moment with {speaker_name or u.speaker_id}",
                                  tick=now, source="self", speaker_id=self.id,
                                  emotion=joy, weight=0.6)
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
        if sim >= CONFIDENCE:
            # kinship grows whenever views are close -- a camp stays cohesive...
            self.affinity[spk] = max(-1.0, min(1.0, cur + AFFINITY_RATE * (sim - CONFIDENCE)))
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
            self.affinity[spk] = max(-1.0, min(1.0, cur - AFFINITY_RATE * (CONFIDENCE - sim)))
            step = -BELIEF_MU * BELIEF_REPEL       # reject: drift away
        return _normalize([v + step * (o - v) for v, o in zip(mine, other)])

    def _weigh_opinion(self, u) -> None:
        """Bounded-confidence update on the LEXICAL belief_vec (Stage-1/2 emergent)."""
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
        turn, where it surfaces as the thing on the agent's mind."""
        self.memory.write(ev.description, tick=now, source="event",
                          speaker_id=None, emotion=ev.emotion)
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
        ctx = SpeechContext(
            name=self.name,
            persona=self.persona,
            mood=mood,
            style=self.style,
            # raw/concept mind: a generous run of the Markov stream, which BECOMES
            # the whole prompt (raw voices it, concept interprets it); normal mode:
            # a couple of fragments as flavour under the persona
            drift=self.thought.current(RAW_DRIFT_N if (self.raw_speech or self.concept_speech) else 2),
            raw_mind=self.raw_speech,
            concept_mind=self.concept_speech,
            memories=[m.text for m in recalled],
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
        )
        return ctx, addressed, mood

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
