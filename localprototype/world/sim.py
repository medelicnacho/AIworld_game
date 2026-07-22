"""The World: tick clock, spatial hearing range, and an urge-based turn scheduler.

Headless and engine-agnostic. Panda3D (or any renderer) will later just subscribe
to the event bus and draw what happens here.
"""

from __future__ import annotations

import math
import random
import sys
import threading
import traceback
import urllib.error
from collections import defaultdict, deque

from agent.agent import REPRO_GRACE
from agent.religion import RELIGIONS
from services.llm import SpeechContext
from world.events import EventBus, Utterance, WorldEvent


HEARING_RANGE = 50.0     # v1: large enough that co-located agents all hear
SPEAK_THRESHOLD = 1.0    # urge needed to grab the floor
RECENT_LINES = 5         # how many recent lines agents are told NOT to repeat
# living reproduction (off unless World(breed_enabled=True), e.g. the viewer)
BREED_GRACE = 0.55       # grace needed to bear a child in life -- only the graceful breed
BREED_INTERVAL = (400, 700)   # ticks between a soul's children (~40-70s at 10Hz)
MATURITY = (500, 800)         # a newborn must live this long before it can breed
# Rebirth (samsara, off by default). Instead of authoring an heir at death, a
# dying stream's explicit self DISSOLVES and only its vasana -- the blurred
# thematic residue of its drift, and its dispositional/opinion lean -- enters a
# BARDO interval, then ripens into a NEW, identity-less stream. No self crosses
# the gap (santana: identity-less causal continuity); population is conserved;
# nothing leaves the wheel except by an intrusion from outside the physics.
BARDO_TICKS = (20, 45)        # dissolution interval between a death and re-coalescing
BOND_VASANA_THRESHOLD = 0.2   # only bonds at least this strong leave a trace across death
DEFAULT_POP_CAP = 10 ** 9     # effectively no cap; the viewer sets a real one
# subconscious murmur: agents occasionally mutter their Markov drift, which seeps
# into nearby minds' memory -> their thought -> their drift (a shared subconscious)
MURMUR_INTERVAL = (12, 28)    # ticks between a soul's murmurs (staggered)
MURMUR_RANGE = 180.0          # how far a murmur carries (quieter than speech)
MURMUR_WEIGHT = 0.3           # how lightly a murmur lands in a listener's memory


def _belief_cos(a, b) -> float | None:
    """How much two souls agree, on the ONE social space the factions, the allies and
    the rift all already read (agent.belief_vec). None when either has no view yet --
    a soul with nothing to disagree about never schisms."""
    from agent.agent import _cosine
    u, v = getattr(a, "belief_vec", None), getattr(b, "belief_vec", None)
    if not u or not v or len(u) != len(v):
        return None
    return _cosine(list(u), list(v))


def _bound(a) -> float:
    """This soul's bounded-confidence engagement bound: engage above it, reject below.
    Under social_genes it is EXPRESSED FROM THE GERM LINE (genome.express_social:
    openness 0 -> 0.85 a narrow mind, openness 1 -> 0.40 a broad one), so how readily a
    soul walks out of a room it disagrees with is a heritable trait. Falls back to the
    world default for any town not running the civ dials."""
    from agent.agent import CONFIDENCE
    return float(getattr(a, "opinion_confidence", CONFIDENCE))


def _agree_gate(a, b) -> bool:
    """True when b's heading must NOT pull a's -- they are far enough apart in belief
    that falling in step would be the very homogenising this fixes. False when either
    has no view: the old proximity herding, unchanged."""
    sim = _belief_cos(a, b)
    return sim is not None and sim < _bound(a)


def _lean(a, b) -> float | None:
    """How much b is A'S PEOPLE, as a signed force in [-1, 1]: +1 we could not agree
    more, 0 exactly at my engagement bound, -1 we are opposites. None when either has
    no view to differ over.

    This is the schism walk's whole idea. Attraction was keyed on AFFINITY, which in a
    town where every soul ends up loving every other (§5.26: 992 warm bonds, median
    trust 0.94, zero enmity -- measured again here at a median 114 bonds per soul) is
    positive almost everywhere. So the pull summed to ~2.5 per soul from every side at
    once and no amount of wanting-to-leave could escape it. Keyed on BELIEF instead,
    the same crowd stops holding a soul it does not agree with, and the mega-herd
    fragments into the like-minded bands its opinions already describe."""
    sim = _belief_cos(a, b)
    if sim is None:
        return None
    bound = _bound(a)
    gap = sim - bound
    # normalised each side of the bound so the full range is used whatever the bound is
    lean = gap / (1.0 - bound) if gap >= 0 else gap / (1.0 + bound)
    return max(-1.0, min(1.0, lean))


class World:
    def __init__(self, bus: EventBus | None = None,
                 events: list[WorldEvent] | None = None,
                 events_enabled: bool = True,
                 move_enabled: bool = False,
                 hearing_range: float = HEARING_RANGE,
                 bounds: tuple[float, float] | None = None,
                 move_seed: int | None = None,
                 breed_enabled: bool = False,
                 pop_cap: int = DEFAULT_POP_CAP,
                 murmur_enabled: bool = False,
                 rebirth_enabled: bool = False) -> None:
        self.bus = bus or EventBus()
        self.agents: list = []
        self.tick = 0
        self.rebirth_enabled = rebirth_enabled   # death -> bardo -> identity-less rebirth
        self._bardo: list[dict] = []             # streams dissolving between lives
        # Wheel-tuning knobs (defaults reproduce the shipped behaviour). The churn
        # isolation (experiment_churn) showed the rebirth wheel, not the opinion
        # space, flattens live --world modularity: bardo dead-time fragments the live
        # cohort and reborn streams re-bond from zero faster than affinity accretes.
        # These let a regime sweep find where factions both FORM and PERSIST across
        # the wheel. bardo_ticks: dissolution interval (shorter -> live pop stays up).
        # vasana_noise: how much the carried opinion/stance lean is scrambled at
        # rebirth (lower -> stronger transmission). reborn_prebond: a stream is born
        # already bonded (this much affinity) to living souls whose lean is close --
        # 'born into its camp', the karmic-transmission lever (0 = bond from scratch).
        self.bardo_ticks = BARDO_TICKS
        self.vasana_noise = 0.06
        # E1 heredity (agent/genome.py): OFF by default -- the wheel re-rolls faculties
        # fresh unless a world opts into a germ line. With it on, a dissolving soul's
        # genome crosses the bardo perturbed once (sigma below) and is expressed onto the
        # newborn stream. No fitness is scored anywhere; selection is E2's, later.
        self.heredity_enabled = False
        self.heredity_sigma = 0.03
        # E2 selection (differential survival; needs stakes + heredity): OFF by default.
        # A soul whose wellbeing stays collapsed past its grace dies EARLY -- and a
        # starved lineage ENDS (no bardo return: differential survival requires that
        # lineages can terminate; the wheel still carries every soul that completes its
        # span). A soul that stays well-fed long enough BREEDS: a new life, the parent's
        # germ line perturbed once. No fitness is scored anywhere -- starvation and
        # plenty are the whole pressure. max_souls is a space bound, not a score.
        self.selection_enabled = False
        self.max_souls = 20
        self._born_live = 0        # births from surplus (distinct from _births, the wheel's)
        # Grief for the fallen: a death LANDS on everyone bonded to the dead -- a charged,
        # appraised memory, tagged as a story seed so the dead can become legends. OFF by
        # default (recorded verdicts predate it); the persistent runner turns it on.
        self.mourning_enabled = False
        # The world's clock (world/clock.py): day/night + seasons + ages of life. OFF by
        # default -- every recorded verdict predates time. The persistent runner turns it
        # on for her town; the season-turn writes a faint ambient memory into every soul.
        self.clock_enabled = False
        # THE LAND (world/regions.py): rich valleys, harsh ridges, per-region commons --
        # the measured requirement (graded, heterogeneous scarcity) made geography.
        # OFF by default: every world that never asks keeps the single commons float.
        self.regions_enabled = False
        self.regions = None
        # WAR (world/war.py): raids over lean granaries -- gated, ecology worlds only
        self.war_enabled = False
        self._war_log: list = []
        # SKIRMISH (world/skirmish.py): brawls between open enemies -- gated, the
        # civilization game's collapse channel (debate -> enmity -> blows)
        self.skirmish_enabled = False
        # CONTACT WAR (world/skirmish.contact_grudge): rival-people warriors breed
        # enmity by PROXIMITY, so two groups that meet on the ground fight over it
        # (warrior-vs-warrior; breeders never take part). Gated, arena only.
        self.contact_war = False
        # MATING (world/mating.py): the civ arena's two-caste reproduction --
        # warriors pair with free breeders, broods gestate, ONE child at term.
        # Default off (THE RULE); when on it is the ONLY birth channel
        # (_selection_tick's surplus budding stands down; starvation stays)
        self.mating_enabled = False
        # how far a child's inherited view leans from its parent's (the W3.5 noise;
        # 0.18 IS today's behaviour -- a knob only so the collapse falsifier can run
        # a frozen-divergence control arm)
        self.culture_noise = 0.18
        # CIV: express the social genes (openness/wrath -> engagement bound / rift
        # scale) on newborns. Off everywhere but the civilization game: the genes
        # ride every genome silently, but only these worlds let them touch the flesh
        self.social_genes = False
        self.day_ticks = 100
        self._last_season = None
        self.reborn_prebond = 0.0
        # Bodhisattva wheel (off by default -> the plain wheel above, which re-rolls wholesome faculties
        # and carries only the thirst). When on, the bardo also carries the CULTIVATED LEAN (grip/prajñā/
        # bodhicitta) faded toward the LIBERATED ground (the buddha-nature tilt), and the thirst is
        # transmuted by bodhicitta (vow vs self-craving) -- so a lineage develops toward buddhahood across
        # lives instead of resetting to ordinary wholesome. The somatic floor runs on these souls too.
        # (agent/path.carry_practice + agent/telos.transmute_thirst; falsified in experiment_bodhisattva.)
        self.bodhisattva_wheel = False
        self.liberation_tilt = 1.0   # tilt strength when on: 0 = neutral mean, 1 = the liberated ground
        # Stage-A stakes: a shared store of provisions under seasonal threat. Off by
        # default; the viewer/experiments turn it on. The commons is what 'work' builds
        # and 'hoard' drains -- the contested thing the affective faculties act on.
        self.stakes_enabled = False
        self.commons = 3.0
        # The functional psyche (PSYCHE.md): when set to an agent.workspace.Workspace,
        # the agents are PARTS OF ONE MIND -- each tick they bid for the floor, the
        # winner is the mind's focus/voice, and the faculty couplings run. Default None:
        # every ordinary world (and saved snapshot) is untouched.
        self.psyche = None
        # Lore (agent/lore.py): souls retell their most salient story -- gossip whose
        # text mutates holder to holder while its provenance tag survives, so a real
        # event can outlive its witnesses as a LEGEND. Off by default.
        self.lore_enabled = False
        # how much of a strong bond's trust survives the bardo as a faint leaning in
        # the reborn stream (0 = love does not survive death; 0.5 = half, faded)
        self.bond_vasana = 0.5
        self.recent: list[str] = []   # rolling buffer of the last things said
        # Recent ATTRIBUTED town lines (speaker_name, text) -- so a reader like Santāna can make
        # meaning of what the souls actually SAY, not only their felt states. Bounded; newest last.
        self.spoken: list[tuple[str, str]] = []
        # Space. Off by default so headless/text runs and tests are unchanged.
        # When on, agents drift each tick under social forces (toward kin, away
        # from foes) and factions become visible spatial clusters. `bounds` is
        # the (w, h) box positions are clamped to; `hearing_range` is how far an
        # utterance carries -- once a faction drifts beyond it, the groups stop
        # talking to each other, which is exactly how an us-vs-them split hardens.
        self.move_enabled = move_enabled
        self.hearing_range = hearing_range
        self.bounds = bounds
        self._rng = random.Random(move_seed)
        # social-force tuning (world units; defaults suit a ~900x600 pixel world)
        self.move_step = 1.4    # overall drift speed
        self.attract = 0.9      # kin pull / foe push strength (scaled by affinity)
        self.repel = 1.5        # personal-space shove so kin cluster but stay readable
        self.min_gap = 72.0     # closer than this and they push apart
        self.wander = 1.0       # random jitter so nobody freezes
        self.center_pull = 0.004  # gentle drift toward center so nobody sticks to a wall
        # HERD ROAMING (off by default; the civ arena turns it on). White-noise
        # wander makes bodies jitter in place; a herd instead carries a shared,
        # slowly-turning HEADING -- each soul keeps its own heading, nudges it
        # toward the average heading of nearby kin (boids alignment), and ambles
        # forward along it. With the existing kin-cohesion + personal-space, that
        # is a herd that drifts across the land together, slowly.
        self.herd_enabled = False
        self.herd_drive = 0.55  # forward amble along the heading (world units, pre-gait)
        self.herd_turn = 0.10   # radians of slow random wander in the heading per tick
        self.herd_align = 0.08  # how hard the heading is pulled to the kin average
        # THE SCHISM WALK (off by default; the civ arena turns it on). Herding is keyed
        # on PROXIMITY and gated only on "not an active foe" -- so movement is BLIND TO
        # BELIEF. Measured on the live arena: opinions were near-random (pairwise cosine
        # mean -0.02, sd 0.67; 70% of pairs far enough apart that the war code calls them
        # different peoples) and the town STILL ambled as three merged herds occupying 8
        # of 24 regions, because disagreement never pushed anybody anywhere. §5.26 found
        # the same shape from the other side: without a source of social differentiation
        # the whole town collapses into one blob.
        #
        # So disagreement becomes a FORCE, in the pull itself (see _lean). A first
        # attempt made it a STATE instead -- a "nomad" flag that walked a leaver out of
        # the crowd -- and it failed on measurement: the escape push was 0.37x the
        # summed pull holding a soul in (0.90 against a median 2.46, from a median 114
        # warm bonds each), so leavers wandered INSIDE the herd and were re-absorbed.
        # 11 souls went nomad over 400 ticks and the biggest clump grew, 59% -> 61%.
        # No state can win against a force field it does not modify, so this modifies
        # the field: a soul is pulled by its people and pushed by everyone else, and
        # going alone is simply what happens when nobody is pulling. The band that
        # forms elsewhere, travels, and gathers compatible strays needs no new
        # machinery -- it is the existing herd code, now keyed on agreement.
        # the attention schema (WORKSPACE_NEXT W1 / RESEARCH C1): a model of the mind's
        # own attention, kept alongside the workspace. Off by default (THE RULE).
        # FORGIVENESS + THE HEARTH CAP -- the two bounds on floored memory (see
        # agent/memory.py). Both default to OFF/uncapped, so §5.28's measured feud
        # behaviour and every saved snapshot are untouched (THE RULE).
        self.parting_enabled = False   # a bloc that has stopped agreeing takes the road
        self.forgive_enabled = False   # souls let dead wounds erode (time + warmth)
        self.hearth_carry = 0          # max floored memories a child inherits; 0 = all
        self.schema_enabled = False
        self.schism_walk = False
        self.schism_push = 1.0    # how hard disagreement repels, relative to the pull
                                  # agreement gives (1.0 = symmetric: the same force,
                                  # signed by whether you are my people)
        # World events are the experiment's perturbations, scheduled by tick.
        # `events_enabled` is the on/off switch: same world, one variable, so a
        # control run (off) and a treatment run (on) differ only by the events.
        self.events_enabled = events_enabled
        self.speak_threshold = SPEAK_THRESHOLD
        self.breed_enabled = breed_enabled   # living reproduction (grace-gated)
        self.pop_cap = pop_cap
        self.murmur_enabled = murmur_enabled   # ambient Markov murmur cross-talk
        self.murmur_range = MURMUR_RANGE
        self.llm = None                        # set by the viewer for collective speech
        self._collective_last: dict[str, str] = {}   # faith id -> its mind's last thought
        self._births = 0   # counter so heirs/children get unique ids
        # Names the wheel has lately spent. A reborn stream coins a name avoiding both
        # the living and this set, so a soul who just dissolved does not come straight
        # back wearing its old name -- it is gone, and forgotten, before any echo of the
        # syllables could recur. Bounded: old names drop off and the space reopens.
        self._spent_names: deque[str] = deque(maxlen=64)
        self._reflect_i = 0   # round-robin cursor for reflect_turn (which soul practices next)
        # Guards shared state when a live viewer drives the three clocks
        # (animate / advance / speak_turn) from different threads. The blocking
        # LLM call is the ONE thing kept outside it, so motion never waits.
        self.lock = threading.RLock()
        self._schedule: dict[int, list[WorldEvent]] = defaultdict(list)
        for ev in events or []:
            self._schedule[ev.tick].append(ev)

    # --- persistence: the whole town can be snapshotted so the wheel survives a restart.
    # The lock (a thread primitive) and the llm/bus (re-injected by the caller) are not saved.
    def __getstate__(self):
        s = self.__dict__.copy()
        s["lock"] = None
        s["llm"] = None
        s["bus"] = None
        return s

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.lock = threading.RLock()
        if self.bus is None:
            self.bus = EventBus()
        # snapshots saved before the functional psyche / lore existed lack the attributes
        self.__dict__.setdefault("psyche", None)
        self.__dict__.setdefault("lore_enabled", False)
        self.__dict__.setdefault("heredity_enabled", False)
        self.__dict__.setdefault("heredity_sigma", 0.03)
        self.__dict__.setdefault("selection_enabled", False)
        self.__dict__.setdefault("max_souls", 20)
        self.__dict__.setdefault("_born_live", 0)
        self.__dict__.setdefault("mourning_enabled", False)
        self.__dict__.setdefault("clock_enabled", False)
        self.__dict__.setdefault("day_ticks", 100)
        self.__dict__.setdefault("_last_season", None)
        self.__dict__.setdefault("regions_enabled", False)
        self.__dict__.setdefault("regions", None)
        self.__dict__.setdefault("war_enabled", False)
        self.__dict__.setdefault("skirmish_enabled", False)
        self.__dict__.setdefault("contact_war", False)
        self.__dict__.setdefault("mating_enabled", False)
        self.__dict__.setdefault("herd_enabled", False)
        self.__dict__.setdefault("herd_drive", 0.55)
        self.__dict__.setdefault("herd_turn", 0.10)
        self.__dict__.setdefault("herd_align", 0.08)
        self.__dict__.setdefault("parting_enabled", False)
        self.__dict__.setdefault("forgive_enabled", False)
        self.__dict__.setdefault("hearth_carry", 0)
        self.__dict__.setdefault("schema_enabled", False)
        self.__dict__.setdefault("schism_walk", False)
        self.__dict__.setdefault("schism_push", 1.0)
        self.__dict__.setdefault("culture_noise", 0.18)
        self.__dict__.setdefault("social_genes", False)
        self.__dict__.setdefault("_war_log", [])

    def _remember_said(self, text: str) -> None:
        self.recent.append(text)
        del self.recent[:-RECENT_LINES]

    def add(self, agent) -> None:
        self.agents.append(agent)

    def _distance(self, a, b) -> float:
        (ax, ay), (bx, by) = a.position, b.position
        return math.hypot(ax - bx, ay - by)

    def listeners_of(self, speaker) -> list:
        return [a for a in self.agents
                if a is not speaker and self._distance(a, speaker) <= self.hearing_range]

    def deliver(self, u: Utterance, speaker) -> None:
        """An utterance is heard by everyone in range -> writes their memory."""
        for listener in self.listeners_of(speaker):
            listener.hear(u, self.tick, speaker_name=speaker.name)
        self._remember_said(u.text)
        self.spoken.append((speaker.name, u.text))   # attributed, for a reader like Santāna
        del self.spoken[:-12]
        self.bus.publish("utterance", u)

    def inject_event(self, ev: WorldEvent) -> None:
        """Fire a world event: every agent in its scope perceives it (writes
        their memory with its emotional charge and nudges them to react). It has
        no speaker -- this is the world happening, not a peer talking, so it is
        NOT added to the anti-echo buffer: agents are meant to reference it."""
        for a in self.agents:
            if ev.scope is not None and a.id not in ev.scope:
                continue
            a.perceive(ev, self.tick)
        self.bus.publish("world_event", ev)

    def inject_user(self, text: str) -> None:
        """User input is just an utterance with source='user'."""
        u = Utterance(speaker_id="user", text=text, tick=self.tick, source="user")
        for listener in self.agents:
            listener.hear(u, self.tick, speaker_name="You")
        self._remember_said(u.text)
        self.bus.publish("utterance", u)

    def step(self, speak: bool = True) -> None:
        # speak=False: advance everything (drift, aging, rebirth, stakes) but do NOT run the
        # inline urge-based speech turn -- a caller can then drive speech off the lock via
        # speak_turn() so a slow (hosted-model) town never freezes the fast wheel.
        self.tick += 1
        # 0) world events scheduled for this tick fire first, so agents perceive
        #    them before this tick's subconscious drift and speech react to them.
        if self.events_enabled:
            for ev in self._schedule.get(self.tick, ()):
                self.inject_event(ev)
        # 1) subconscious + living memory for everyone
        for a in self.agents:
            for ev in a.step(self.tick):
                self.bus.publish("memory", (a.id, ev))
        # 1.5) stakes: consume/act/hardship on the shared provisions (real loss the
        #      affective faculties then meet), before anyone speaks of it
        if self.stakes_enabled:
            from world import stakes
            stakes.step(self)
        # 1.7) the global workspace: parts bid for the mind's floor; the winner gains
        #      the urge to speak BEFORE this tick's floor is contested below
        if self.psyche is not None:
            self.psyche.step(self)
        # 1.8) lore: souls retell their stories (gossip -> legend), memory-only like murmur
        if self.lore_enabled:
            from agent import lore
            lore.retell(self)
        # 2) urge-based turn: highest urge over threshold grabs the floor
        ready = [a for a in self.agents if a.wants_to_speak(self.speak_threshold)] if speak else []
        if ready:
            speaker = max(ready, key=lambda a: a.speak_urge)
            # tell the speaker what was just said (others' lines) so it won't echo
            recent = [t for t in self.recent if t][-RECENT_LINES:]
            # A turn must never abort the clock. The LLM call is already contained
            # in Agent.speak; this is the outer net for anything else in the turn.
            try:
                u = speaker.speak(self.tick, recent=recent)
                self.deliver(u, speaker)
            except Exception:  # noqa: BLE001 -- contain, log, keep ticking
                print(f"[sim] turn for '{speaker.id}' failed at tick {self.tick}:",
                      file=sys.stderr)
                traceback.print_exc()
                speaker.speak_urge = 0.0   # back off so a broken agent isn't retried every tick
        # 2.5) aging: the old die. A soul that dies in grace reproduces an heir;
        #      a fallen soul dies heirless, so the realm selects for the faithful.
        if self.clock_enabled:
            self._clock_tick()
        self._reap()
        if self.selection_enabled and self.stakes_enabled:
            self._selection_tick()   # E2: starvation ends lineages; surplus starts them
        self._process_bardo()    # streams ripen out of the bardo into new lives
        if self.breed_enabled and not self.rebirth_enabled:   # living reproduction
            self._breed()
        # 2.55) WAR (gated, ecology worlds): every RAID_CHECK ticks the land asks
        # whether anyone is hungry enough to march (world/war.py -- raids over lean
        # granaries; the muster decides who goes; the dead are mourned and END).
        if self.war_enabled and self.tick > 0:
            from world import war as _war
            # raid cadence is per-world (the civilization game runs war hot; every
            # older world keeps the module default -- THE RULE)
            if self.tick % getattr(self, "raid_check", _war.RAID_CHECK) == 0:
                _war.war_tick(self)
        # 2.56) SKIRMISH (gated, the civilization game): every SKIRMISH_CHECK ticks
        # the angry close on their enemies and quarrels past words come to blows
        # (world/skirmish.py -- children never fight; the worn disengage; the rare
        # dead are mourned and their lineages end).
        if self.skirmish_enabled and self.tick > 0:
            from world import skirmish as _skirmish
            if self.tick % _skirmish.SKIRMISH_CHECK == 0:
                # contact aggression FIRST, so a fresh on-sight grudge can drive this
                # same tick's confrontation: two peoples that just met come to blows
                if getattr(self, "contact_war", False):
                    _skirmish.contact_grudge(self)
                _skirmish.skirmish_tick(self)
        # 2.57) MATING (gated, the civ arena): every MATE_CHECK ticks the broods
        # count down (births at term) and fed grown warriors pair with free
        # breeders (world/mating.py -- welfare invariants in its docstring FIRST;
        # breeders are never harmed; rivalry lands warrior-on-warrior only).
        if getattr(self, "mating_enabled", False) and self.tick > 0:
            from world import mating as _mating
            if self.tick % _mating.MATE_CHECK == 0:
                _mating.mating_tick(self)
        # 2.58) THE PARTING (gated): a bloc whose view has settled past the rift from
        # the town's own takes its own road as a band -- the one road from "factions
        # emerge" to "bands roam the wild" (world/parting.py; welfare invariants in its
        # docstring FIRST -- breeders keep the hearth, children never part, the worn stay,
        # and nothing here writes hostility).
        if getattr(self, "parting_enabled", False) and self.tick > 0:
            from world import parting as _parting
            _parting.parting_tick(self)
        # 2.6) bodies move: drift under social forces so factions take territory.
        # At night the town is HOME -- bodies rest where they stand (labour already
        # pauses; wandering does too).
        if self.move_enabled:
            from world import clock as _clock
            if not (self.clock_enabled
                    and _clock.is_night(self.tick, self.day_ticks)):
                self._drift_positions()
        # 3) tick heartbeat: a boundary marker so telemetry/renderers can snapshot
        #    the world's state once everything that happened this tick has settled.
        self.bus.publish("tick", self.tick)

    def _reap(self) -> None:
        """Death of old age. Two cosmologies: with rebirth OFF, a soul that died
        in grace authors an heir and the fallen die heirless (the selection layer);
        with rebirth ON there is no judge and no author -- every stream dissolves
        into the bardo, to ripen later as a new identity-less stream."""
        survivors = []
        for a in self.agents:
            if a.age < a.lifespan:
                survivors.append(a)
                continue
            if self.rebirth_enabled:
                self._mourn(a)                    # the loss lands on those who loved them
                self._dissolve(a)                 # into the bardo; no heir, no author
            elif getattr(self, "mating_enabled", False):
                # civ arena: mating drives ALL births, this channel included -- an
                # age-death ends heirless (the germ line continues only through the
                # pairs made in life). Without this gate the heir channel pinned the
                # population at the cap (pairing starved for room forever) and every
                # breeder's heir woke a default-caste warrior: the breeding caste
                # went EXTINCT by the second generation (measured, the 3000-tick arc).
                self._mourn(a)                    # mourned like any other death
            elif a.grace >= REPRO_GRACE:
                self._births += 1
                heir = a.reproduce(f"{a.id}.{self._births}")
                self._endow_heir(a, heir)         # germ line + worldview cross too
                survivors.append(heir)            # the heir takes the parent's place
                self.bus.publish("birth", heir.id)
            self.bus.publish("death", a.id)       # the stream, as it was, ends
        self.agents = survivors

    def _endow_heir(self, parent, heir) -> None:
        """What an heir carries besides the name. Agent.reproduce() passes persona,
        faith, and the self-narrative -- but it was leaving the heir GERMLESS and
        VECTORLESS (found the hard way: in the ecology every grace-death of old age
        replaced a soul with an heir holding no genome and no worldview, so factions
        starved to loners within three generations and selection silently reset on
        the age-death channel -- the G2 trace of 2026-07-04). GERM: the parent's
        line, perturbed once, expressed on the body (gated by heredity_enabled: the
        old wheel town's heirs keep their own dials). CULTURE: the parent's view
        with noise -- the same lean-never-a-copy _birth_from gives every child."""
        if self.heredity_enabled:
            from agent.genome import express, from_agent, inherit
            pg = getattr(parent, "genome", None) or from_agent(parent, self._rng)
            heir.genome = inherit(pg, self._rng, parent.id, sigma=self.heredity_sigma)
            express(heir.genome, heir)
        if getattr(parent, "belief_vec", None) is not None:
            noisy = [v + self._rng.gauss(0.0, self.culture_noise)
                     for v in parent.belief_vec]
            norm = sum(v * v for v in noisy) ** 0.5 or 1.0
            heir.belief_vec = tuple(v / norm for v in noisy)
            heir.bond_enabled = True
        # the rift is cultural too: a child raised where argument wounds learns
        # that arguments wound (gated by the parent, so old towns stay untouched);
        # so is how open a mind is (default = the old global, THE RULE)
        heir.rift_enabled = getattr(parent, "rift_enabled", False)
        heir.forgive_enabled = getattr(parent, "forgive_enabled", False)  # ... and whether
                                       # a dead wound is allowed to close in this line
        heir.bond_creed = getattr(parent, "bond_creed", False)    # and whether a shared
                                       # view is what warms a bond -- carried like the rift,
                                       # or the mechanic dies with the founding cast (the
                                       # arena turns its founders over completely)
        if hasattr(parent, "opinion_confidence"):
            heir.opinion_confidence = parent.opinion_confidence
        if self.social_genes and getattr(heir, "genome", None) is not None:
            from agent.genome import express_social
            express_social(heir.genome, heir)   # the GENE outranks the parent's phenotype
        self._hearth(parent, heir)

    def _hearth(self, parent, child) -> None:
        """A child is raised on the house's open wounds. The square's retelling
        (lore.py) is a lottery -- each soul tells only its TOP story, and in a town
        where someone dies every few ticks, fresh mourning-lore always outbids an
        old floored grievance (measured: the feud reached 18 non-founders by t=200
        and was extinct by t=400 anyway, because generation three never heard it).
        But a feud is not kept by the SQUARE; it is kept by the HEARTH: the stories
        a house will not let die are told to its children before the town gets a
        word in. So the parent's floored memories (salience_floor > 0 -- grievances)
        cross at birth, in the words the parent CURRENTLY carries (legend dynamics:
        drifted text, same tag), source='lore' so provenance stays honest (a story
        received, not lived -- C14 reads it exactly right)."""
        wounds = [m for m in parent.memory.items
                  if getattr(m, "salience_floor", 0.0) > 0.0]
        # THE CAP: a child is raised on the house's LOUDEST wounds, not its every wound.
        # Uncapped, this line is the compounding term behind the memory ratchet -- each
        # birth copies the parent's whole grievance ledger, so floored items multiply down
        # the generations instead of merely persisting (measured: 6 -> 217 over 2000 ticks
        # once war started, doubling ~every 500). Capped, a feud still crosses at birth in
        # the parent's drifted words -- §5.16's legend dynamics and §5.28's G2 both ride on
        # the strongest stories, which are exactly the ones kept. 0 = uncapped (the old
        # behaviour, and the default: THE RULE).
        cap = getattr(self, "hearth_carry", 0)
        if cap > 0 and len(wounds) > cap:
            wounds = sorted(wounds, key=lambda m: m.salience, reverse=True)[:cap]
        for m in wounds:
            child.memory.write(m.text, tick=self.tick, source="lore",
                               speaker_id=parent.id, weight=0.9,
                               lore_id=getattr(m, "lore_id", ""),
                               salience_floor=m.salience_floor)

    def _mourn(self, dead) -> None:
        """The death LANDS: every living soul that loved the dead writes a charged memory
        of the loss -- appraised against its days (shock after good ones, something braced
        for mid-slide, §5.15), weighted by how deep the bond ran, and TAGGED as a story
        seed (lore) so a mourned name can outlive its mourners as legend (§5.16). Enmity
        does not mourn; it notes, colder and quieter, that the quarrel is over. Only what
        was actually bonded feels anything: a stranger's death is weather."""
        if not self.mourning_enabled:
            return
        for a in self.agents:
            if a is dead or not a.bond_enabled:
                continue
            b = a.bonds.get(dead.id)
            if b is None or abs(b.trust) < BOND_VASANA_THRESHOLD:
                continue
            if b.trust > 0:
                emo = -0.4 - 0.4 * b.trust           # grief, deep as the love was
                text = f"{dead.name} is gone from us, and I loved them"
            else:
                emo = -0.1                            # an enemy's death: colder, stranger
                text = f"{dead.name} is gone, and our quarrel died unsettled"
            if getattr(a, "expect_enabled", False):
                from agent import expectation as _expectation
                emo = _expectation.appraise_event(a, emo)
            a.memory.write(text, tick=self.tick, source="event", speaker_id=dead.id,
                           emotion=emo, weight=1.3, lore_id=f"death:{dead.id}:{self.tick}")

    def _dissolve(self, soul) -> None:
        """A stream dies: its explicit self (name, story) dissolves, but its vasana
        -- the blurred, impersonal residue of its Markov drift, plus its opinion and
        dispositional lean -- enters the bardo. The autobiography does NOT cross:
        only the thematic/karmic tendency does, so no self is transmitted."""
        seeds = [f for f in soul.thought.drift if f][-5:]
        if not seeds:                              # fall back to faint memory fragments
            seeds = [m.text for m in soul.memory.recall(k=3)]
        # A bond-trace may cross too: not the memory of WHOM, but a residual leaning
        # toward (or away from) those the dead soul felt strongly about -- love as a
        # karmic tendency (vasana), not autobiography. Only strong bonds leave a
        # trace; faint ones dissolve completely. Carried per-target id, so it only
        # resolves if that other is still alive when the new stream wakes.
        bond_trace = ({tid: b.trust for tid, b in soul.bonds.items()
                       if abs(b.trust) >= BOND_VASANA_THRESHOLD}
                      if (self.bond_vasana > 0 and soul.bond_enabled) else {})
        self._bardo.append({
            "seeds": seeds,
            "belief_vec": list(soul.belief_vec) if soul.belief_vec is not None else None,
            "stance_vec": list(soul.stance_vec) if soul.stance_vec is not None else None,
            "temperament": max(-1.0, min(1.0, soul.temperament + self._rng.uniform(-0.25, 0.25))),
            "position": soul.position,
            "bonds": bond_trace,
            "countdown": self._rng.randint(*self.bardo_ticks),
            "lifespan": soul.lifespan,   # the new stream lives on the lineage's scale
            # the THIRST that crosses the bardo (Second Noble Truth): the drive scaled by how
            # tightly this soul clung -- a hungry death pulls the next life on; wisdom lets it rest.
            "telos": getattr(soul, "telos", 0.0),
            "eff_grip": soul.effective_grip(),
            # the cultivated lean -- the vāsanā of practice the bodhisattva wheel carries (ignored by
            # the plain wheel, which re-rolls faculties fresh): grip/prajñā/bodhicitta as the soul died.
            "grip": soul.grip,
            "prajna": soul.prajna,
            "bodhicitta": getattr(soul, "bodhicitta", 0.0),
            # psyche mode: the FUNCTION re-arises even as the drive fades -- a mind does
            # not lose its capacity to grieve when a particular grief passes
            "psyche_faculty": getattr(soul, "psyche_faculty", ""),
        })
        if self.heredity_enabled:
            # E1: the germ line crosses, perturbed ONCE at the bardo (agent/genome.py).
            # A founder that never carried an explicit genome gets one captured from the
            # dials it lived with -- so heredity can be switched on over a running town.
            from agent import genome as _genome
            g = getattr(soul, "genome", None) or _genome.from_agent(soul, self._rng)
            self._bardo[-1]["genome"] = _genome.inherit(g, self._rng, soul.id,
                                                        sigma=self.heredity_sigma)
        self.bus.publish("dissolution", soul.id)

    def _clock_tick(self) -> None:
        """The lived year: at each turn of season, a faint ambient memory enters every
        soul (the year is FELT, and can surface in speech and gossip); and the elders'
        story-memories are shielded from decay -- the old remember the old stories,
        which is how a town keeps its legends long enough to outlive their witnesses."""
        from world import clock as _clock
        season_now = _clock.season(self.tick, self.day_ticks)
        if season_now != self._last_season:
            first = self._last_season is None      # birth of the world: no announcement
            self._last_season = season_now
            if not first:
                text, emo = _clock.SEASON_TURN[season_now]
                for a in self.agents:
                    a.memory.write(text, tick=self.tick, source="event", emotion=emo,
                                   lore_id=f"season:{season_now}:{self.tick}")
        for a in self.agents:
            if _clock.stage(a.age, a.lifespan) == "elder":
                for m in a.memory.items:
                    if m.lore_id and m.salience < _clock.ELDER_LORE_FLOOR:
                        m.salience = _clock.ELDER_LORE_FLOOR

    # --- E2: differential survival (EVOLUTION.md stage E2) --------------------------------
    STARVE_MET = 0.5         # a tick with less than half one's need met counts as UNFED --
                             # survival reads actual food (stakes' met), NOT wellbeing:
                             # 'tend' can soothe a feeling but not a stomach, and the first
                             # test run proved a soul would otherwise self-soothe forever
                             # on nothing (recorded; the affect stays the affect)
    STARVE_GRACE = 25        # ticks of starvation a soul weathers before the hazard opens
    STARVE_HAZARD = 0.02     # per-tick death chance per starved tick past the grace
    BREED_CEIL = 0.75        # wellbeing above this counts as thriving
    BREED_TICKS = 60         # sustained thriving before a birth
    BIRTH_COST = 0.3         # provisions the parent gives the newborn (birth is not free)

    def _selection_tick(self) -> None:
        """No fitness is scored: this reads only what the stakes already made true.
        Starvation that outlasts the grace opens a rising death hazard -- and a starved
        death ENDS the lineage (no bardo: differential survival requires terminable
        lineages; age-deaths still ride the wheel). Sustained surplus earns a BIRTH:
        a new soul carrying the parent's germ line, perturbed once, at real cost."""
        survivors = []
        from world import clock as _clock
        for a in self.agents:
            starving = getattr(a, "_met", 1.0) < self.STARVE_MET
            a._starved_ticks = (getattr(a, "_starved_ticks", 0) + 1) if starving else 0
            over = a._starved_ticks - self.STARVE_GRACE
            if self.clock_enabled and _clock.stage(a.age, a.lifespan) == "child":
                over = 0    # the welfare floor's spirit, applied to the smallest: children
                            # go hungry but the hazard never opens on them (their PARENTS'
                            # deaths are how famine reaches a family in this world)
            if over > 0 and self._rng.random() < min(0.5, self.STARVE_HAZARD * over):
                self.bus.publish("starvation", a.id)   # loud: an ended lineage is an event
                self._mourn(a)                         # and a mourned one: hunger has faces
                continue                               # no bardo entry: the lineage ends
            survivors.append(a)
        self.agents = survivors
        if getattr(self, "mating_enabled", False):
            return   # civ arena: ALL births go through the mating system (world/
                     # mating.py) -- a second birth channel here would double the
                     # population; the starvation hazard above still ran (E2's deaths)
        if len(self.agents) + len(self._bardo) >= self.max_souls:
            return   # space, not score -- and the wheel's PENDING returns count toward it
                     # (the probe caught pop 17 of 16: a rebirth owed is a mouth owed)
        for a in list(self.agents):
            fed = a.wellbeing > self.BREED_CEIL and a.stores > self.BIRTH_COST
            a._fed_ticks = (getattr(a, "_fed_ticks", 0) + 1) if fed else 0
            if a._fed_ticks >= self.BREED_TICKS:
                a._fed_ticks = 0
                self._birth_from(a)
                if len(self.agents) + len(self._bardo) >= self.max_souls:
                    break

    def _birth_from(self, parent) -> None:
        """A birth (not a rebirth): a NEW soul, fresh name and subconscious, the parent's
        germ line inherited with one mutation, provisioned from the parent's stores, and
        bonded to the parent from the first breath. This is the asexual-budding door;
        the body lives in _spawn_child, shared with the mating system."""
        self._spawn_child(parent)

    def _spawn_child(self, parent, genome=None, caste: str = "warrior"):
        """THE ONE SPAWN PATH: asexual budding (_birth_from, E2's surplus channel) and
        the mating system (world/mating.py) both land here. With genome=None the child
        inherits the parent's germ line perturbed once -- at the same point in the
        CALL order as the pre-refactor code, so waking state and call sequence are
        unchanged for old worlds (honest caveat: genome.DIALS gained two dials, so
        inherit()'s per-call draw COUNT differs across code versions -- an old
        snapshot wakes identical but its exact continuation stream diverges; see the
        genome.py note). Mating passes the two-parent crossed genome explicitly.
        Returns the child (or None if the world has no voice to give it)."""
        from agent.agent import Agent
        from agent.bond import Bond
        from agent.genesis import ROLES, coined_name, endow_faculties
        from agent.genome import from_agent, inherit, express
        from agent import telos as _telos
        if self.llm is None:
            return None
        self._born_live += 1
        living = {x.name for x in self.agents}
        name = coined_name(self._rng, taken=living | set(self._spent_names))
        self._spent_names.append(name)
        sid = f"born:{self._born_live}"
        px, py = parent.position
        a = Agent(sid, name, (px + self._rng.uniform(-15, 15), py + self._rng.uniform(-15, 15)),
                  f"You are {name}, a soul who speaks your own mind.",
                  [f"I am {name}, born to this town"], self.llm,
                  seed=self._rng.randint(0, 10 ** 6), temperament=parent.temperament,
                  lifespan=parent.lifespan)   # the lineage's scale, like the wheel
        role, tasks = self._rng.choice(ROLES)
        a.role, a.task = role, self._rng.choice(tasks)
        endow_faculties(a, self._rng)
        # a child bonds in the space its parent bonds in: an opinion-space town
        # (stanceless souls -- the ecology/civilization worlds) must not have its
        # children re-seeded with stances, or hear() routes their social learning
        # into a space no faction read ever sees (caught by the collapse probe:
        # the rift never fired because the stance path shadowed the opinion path)
        if getattr(parent, "stance_vec", None) is None:
            a.stance_vec = None
        a.aim = _telos.fresh_aim(role)
        a.caste = caste
        if genome is None:   # asexual budding: the parent's line, perturbed once
            pg = getattr(parent, "genome", None) or from_agent(parent, self._rng)
            genome = inherit(pg, self._rng, parent.id, sigma=self.heredity_sigma)
        a.genome = genome
        express(a.genome, a)
        # CULTURAL INHERITANCE (the war falsifier's discovery): without this, blocs
        # dissolve within one generation -- newborns held NO worldview, factions
        # starved to loners, and wars stopped for amnesia, not peace. A child absorbs
        # its parent's view WITH NOISE (the vasana spirit: a lean, never a copy);
        # worlds without opinion dynamics are untouched (parent has no vector).
        if getattr(parent, "belief_vec", None) is not None:
            noisy = [v + self._rng.gauss(0.0, self.culture_noise)
                     for v in parent.belief_vec]
            norm = sum(v * v for v in noisy) ** 0.5 or 1.0
            a.belief_vec = tuple(v / norm for v in noisy)
        a.bond_enabled = True
        a.self_model_enabled = True
        # the parent provisions the child -- birth costs the parent something real
        give = min(self.BIRTH_COST, parent.stores)
        parent.stores -= give
        a.stores = give
        a.wellbeing = 0.6
        a.bonds.setdefault(parent.id, Bond()).warm(0.8)
        parent.bonds.setdefault(a.id, Bond()).warm(0.8)
        a.rift_enabled = getattr(parent, "rift_enabled", False)   # cultural, like the view
        a.forgive_enabled = getattr(parent, "forgive_enabled", False)  # ... and whether it forgives
        a.bond_creed = getattr(parent, "bond_creed", False)       # ... and so is what warms it
        if hasattr(parent, "opinion_confidence"):                 # and how open a mind is
            a.opinion_confidence = parent.opinion_confidence
        if self.social_genes:
            from agent.genome import express_social
            express_social(a.genome, a)         # the GENE outranks the parent's phenotype
        self._hearth(parent, a)     # the house's open wounds are told to the child
        self.agents.append(a)
        self.bus.publish("birth", a.id)
        return a

    def _process_bardo(self) -> None:
        """Ripen the bardo: each dissolving stream counts down, then re-coalesces
        into a new, identity-less stream seeded by its vasana -- continuity without
        a self (santana)."""
        if not self._bardo:
            return
        still = []
        for entry in self._bardo:
            entry["countdown"] -= 1
            if entry["countdown"] > 0:
                still.append(entry)
            else:
                self._coalesce(entry)
        self._bardo = still

    def _coalesce(self, entry: dict) -> None:
        """A new stream condenses out of the bardo's residue. It gets a merely
        designated name (no story), a fresh subconscious, and the vasana as faint
        memory it drifts over -- surfacing as ITS OWN, with no knowledge of whose
        it was. The opinion lean persists (perturbed), so a faction can outlive its
        members through karmic transmission, not inherited labels."""
        from agent.agent import Agent, _normalize
        from agent.genesis import ROLES, coined_name, endow_faculties
        from agent import telos as _telos
        if self.llm is None:
            return
        self._births += 1
        # psyche mode: the dying stream was a PART OF ONE MIND. What re-arises is a new
        # DRIVE carrying the departed part's FUNCTION (its faculty), wearing a fresh
        # drive-name -- never a townsperson with a trade dreamed into a psyche.
        fac = entry.get("psyche_faculty", "")
        in_psyche = self.psyche is not None and bool(fac)
        # A name coined fresh from nothing -- never the same soul dying over and over, but
        # a different one born each turn, avoiding both the living and the lately-departed
        # (which then fade from _spent_names and from others' decaying memories alike).
        living = {a.name for a in self.agents}
        if in_psyche:
            from agent import psyche as _psyche
            name = _psyche.coined_drive(self._rng, taken=living | set(self._spent_names))
        else:
            name = coined_name(self._rng, taken=living | set(self._spent_names))
        self._spent_names.append(name)
        sid = f"stream:{self._births}"
        seeds = entry["seeds"] or ["something stirs in the quiet"]
        if in_psyche:
            func = _psyche.FUNCTION_OF.get(fac, "a nameless stirring in us")
            persona = f"You are {name}, {func} -- a part of one mind, not a person."
        else:
            persona = f"You are {name}, a soul who speaks your own mind."
        a = Agent(sid, name, entry["position"], persona,
                  list(seeds), self.llm, seed=self._rng.randint(0, 10 ** 6),
                  temperament=entry["temperament"],
                  lifespan=entry.get("lifespan", 2000))   # not the default 60!
        a.belief = max(seeds, key=len)   # a nascent stance from the strongest vasana
        if in_psyche:
            # the FUNCTION is the identity: differential endowment, the faculty carried
            # loud again. The bodhisattva-carry is bypassed on purpose -- it would fade
            # Dread's grip toward the liberated ground and dissolve the part's very organ.
            a.role, a.task = func, ""
            _psyche.endow_part(a, fac, self._rng)
            a.aim = _psyche.AIM_OF.get(fac, "")
        else:
            role, tasks = self._rng.choice(ROLES)   # a new life, a new trade in the realm
            a.role, a.task = role, self._rng.choice(tasks)
            # the reborn stream wakes a FULL soul (the standard affective endowment -- compassion,
            # ground, joy, prajñā…), with a FRESH aim from its new trade (anatta: the dead soul's
            # project does NOT cross), driven by the carried THIRST -- a clinging death wakes hungry,
            # a wise one at rest. Only the disposition transmigrates; the faculties begin fresh, so no
            # stream is doomed to its predecessor's exact kleśas.
            endow_faculties(a, self._rng)
            a.aim = _telos.fresh_aim(role)
            if self.heredity_enabled and entry.get("genome") is not None:
                # E1: heredity overrides the fresh re-roll -- the lineage's dials descend.
                # Deliberate precedence: the bodhisattva carry BELOW still outranks the
                # germ line for grip/prajna/bodhicitta (cultivation is not heredity, and
                # the Path's validated carry keeps its organ); telos stays with the
                # THIRST channel (§5.5) for the same reason.
                from agent.genome import express as _express_genome
                a.genome = entry["genome"]
                _express_genome(a.genome, a)
        if self.bodhisattva_wheel and not in_psyche:
            # carry the CULTIVATED LEAN across the bardo, faded toward the liberated ground (the
            # buddha-nature tilt), overriding the fresh endowment's wisdom wing -- so practice and the
            # lineage's drift toward liberation persist instead of resetting. Bodhicitta is carried too;
            # the thirst is transmuted by it (the vow, not self-craving). The somatic floor runs here.
            from agent import path as _path
            a.grip, a.prajna, a.bodhicitta = _path.carry_practice(
                entry.get("grip", a.grip), entry.get("prajna", a.prajna),
                entry.get("bodhicitta", a.bodhicitta), self._rng, self.liberation_tilt)
            a.telos = _telos.transmute_thirst(entry.get("telos", 0.0), a.effective_grip(), a.bodhicitta)
            a.somatic_enabled = True       # the bottom-up floor active in the live world
            a.cultivate_enabled = True     # within-life practice grooves the faculties ...
            a.reflect_enabled = True       # ... fed by reflect_turn(), so the soul EARNS the lean, not only inherits it
        elif not in_psyche:
            a.telos = _telos.reborn_telos(entry.get("telos", 0.0), entry.get("eff_grip", 0.0))
        for frag in seeds:
            a.memory.write(frag, tick=self.tick, source="self", speaker_id=sid, weight=0.8)
        if entry["belief_vec"] is not None:
            # gentle perturbation: the lean PERSISTS, softened by the dissolution
            # (small per-component noise -- in a high-dim space even this spreads)
            noise = [self._rng.gauss(0.0, self.vasana_noise) for _ in entry["belief_vec"]]
            a.belief_vec = _normalize([v + n for v, n in zip(entry["belief_vec"], noise)])
            a.belief_grounded = True
        if entry.get("stance_vec") is not None:
            # the SIGNED stance lean is the lever that actually drives the graph, so
            # carrying it (perturbed) is how a faction outlives its members: the new
            # stream wakes leaning the same way, with no memory of whose lean it was.
            snoise = [self._rng.gauss(0.0, self.vasana_noise) for _ in entry["stance_vec"]]
            a.stance_vec = _normalize([v + n for v, n in zip(entry["stance_vec"], snoise)])
        a.introspect_chance = 0.25
        # the reborn stream carries the faculties of a self: it relates (bonds) and it
        # takes stock of who it is becoming (self-model). Crucially the self-model is
        # NOT carried across -- only the vasana (blurred drift, opinion, stance) is, so
        # any self that re-coheres does so from the impersonal residue, not a transmitted
        # autobiography. Whether it re-coheres toward the dead self is the open question.
        a.bond_enabled = True
        a.self_model_enabled = True
        # Does love survive death? A faded bond-trace toward those still living wakes
        # in the new stream as a leaning with no history and no wounds -- it is drawn
        # to (or wary of) someone it cannot remember ever knowing. Anatta: the self is
        # gone, the tendency persists. One-directional (the other does not know).
        if entry.get("bonds"):
            from agent.bond import Bond
            a.bond_enabled = True
            living = {x.id for x in self.agents}   # a not appended yet
            for tid, trust in entry["bonds"].items():
                if tid in living:
                    faded = trust * self.bond_vasana
                    if abs(faded) >= 0.01:
                        a.bonds[tid] = Bond(trust=faded)
        self.agents.append(a)
        self._prebond(a)   # optionally born already bonded into its opinion-camp
        self.bus.publish("rebirth", sid)

    def _prebond(self, newcomer) -> None:
        """Karmic-transmission lever: a reborn stream wakes already bonded to the
        living souls whose opinion/stance lean matches its inherited one, instead of
        re-bonding from zero. With reborn_prebond>0 a faction can outlive its members
        because each new body is born INTO the camp its vasana carried. Mutual
        (both directions) so it registers as a real edge in factions.blocs."""
        if self.reborn_prebond <= 0.0:
            return
        mine = newcomer.stance_vec if newcomer.stance_vec is not None else newcomer.belief_vec
        if mine is None:
            return
        for other in self.agents:
            if other is newcomer:
                continue
            theirs = other.stance_vec if other.stance_vec is not None else other.belief_vec
            if theirs is None or len(theirs) != len(mine):
                continue
            sim = sum(x * y for x, y in zip(mine, theirs))   # both are unit vectors
            if sim > 0:   # aligned lean -> born as kin, proportional to how aligned
                bond = self.reborn_prebond * sim
                newcomer.affinity[other.id] = max(newcomer.affinity.get(other.id, 0.0), bond)
                other.affinity[newcomer.id] = max(other.affinity.get(newcomer.id, 0.0), bond)

    def _breed(self) -> None:
        """Living reproduction: a graceful, mature soul bears a child beside it
        every so often, up to the population cap. Grace GATES it, so the devout
        and the virtuous out-populate the fallen over generations. Children are
        born next to their parent, so lineages clump into spatial colonies."""
        spawned: list = []
        for a in self.agents:
            a.breed_cooldown -= 1
            if (a.breed_cooldown <= 0 and a.grace >= BREED_GRACE
                    and len(self.agents) + len(spawned) < self.pop_cap):
                self._births += 1
                child = a.reproduce(f"{a.id}~{self._births}")
                self._endow_heir(a, child)        # germ line + worldview cross too
                ox, oy = self._rng.uniform(-45, 45), self._rng.uniform(-45, 45)
                child.position = (a.position[0] + ox, a.position[1] + oy)
                child.breed_cooldown = self._rng.randint(*MATURITY)   # must mature first
                a.breed_cooldown = self._rng.randint(*BREED_INTERVAL)  # parent waits to breed again
                spawned.append(child)
                self.bus.publish("birth", child.id)
        self.agents.extend(spawned)

    def _murmur(self) -> None:
        """The subconscious aloud. Some souls (staggered) mutter their current
        Markov drift fragment; it seeps -- lightly -- into nearby minds' memory,
        which feeds their thought, which colours their own drift. A shared,
        drifting subconscious that the renderer can also voice as room murmur.
        Deliberately NOT routed through hear(): it touches memory/thought/mood
        only, never the deliberate-speech machinery (faith, grace, ideology)."""
        for a in self.agents:
            a.murmur_cooldown -= 1
            if a.murmur_cooldown > 0:
                continue
            a.murmur_cooldown = self._rng.randint(*MURMUR_INTERVAL)
            frag = a.thought.current(1)
            frag = frag[0] if frag else ""
            if not frag:
                continue
            for b in self.agents:
                if b is not a and self._distance(a, b) <= self.murmur_range:
                    b.memory.write(frag, tick=self.tick, source="murmur",
                                   speaker_id=a.id, weight=MURMUR_WEIGHT)
            self.bus.publish("murmur", (a.id, frag))

    def _drift_positions(self) -> None:
        """Move every body one step under social forces: pulled toward those it
        feels kinship with, pushed from those it feels enmity for, plus a shove
        out of anyone's personal space and a little wander. Run each tick when
        movement is enabled; over time like clusters with like and the factions
        the affinity ledger formed become territory you can see on the map.
        """
        if len(self.agents) < 2:
            return
        # a big town cannot afford every-pair forces (O(n^2)); past ~48 souls each body
        # weighs its BONDED ones (the relationship group -- these are what make knots
        # roam together) plus a small random sample of the crowd (ambient personal
        # space / strangers' enmity). Small towns keep the exact original physics --
        # the faction experiments were validated on it.
        big = len(self.agents) > 48
        by_id = {b.id: b for b in self.agents} if big else None
        # mate-guarding (civ arena only): a warrior that has paired is drawn back
        # toward its hearth's breeder, so warriors cluster protectively around
        # their brood -- and rivals who wander in meet the grudge (mating.py)
        guard = getattr(self, "mating_enabled", False)
        if guard:
            from world import mating as _mating
            gid = by_id or {b.id: b for b in self.agents}
        herd = getattr(self, "herd_enabled", False)
        schism = getattr(self, "schism_walk", False)
        for a in self.agents:
            ax, ay = a.position
            fx = fy = 0.0
            align_x = align_y = 0.0    # herd: kin heading resultant (boids alignment)
            if big:
                others = [by_id[i] for i in getattr(a, "bonds", {}) if i in by_id]
                others += self._rng.sample(self.agents, min(16, len(self.agents)))
            else:
                others = self.agents
            for b in others:
                if b is a:
                    continue
                bx, by = b.position
                dx, dy = bx - ax, by - ay
                d = math.hypot(dx, dy) or 1.0
                ux, uy = dx / d, dy / d
                # social force, faded by distance. Kinship reaches FAR (twice
                # hearing range) so a stray can always find its way back to its
                # people; enmity is SHORT-range so foes stop shoving once apart
                # rather than flinging each other to the walls. Long-range pull +
                # short-range push is what keeps the camps stable clusters.
                aff = a.feels_about(b.id)
                # THE SCHISM WALK: under it, what moves a body is AGREEMENT, not mere
                # absence of enmity -- so a soul is held by its people and by nobody
                # else. Real enmity still repels at least as hard as disagreement does
                # (an enemy you happen to agree with is still an enemy).
                pull = aff
                if schism:
                    lean = _lean(a, b)
                    if lean is not None:
                        lean *= self.schism_push if lean < 0 else 1.0
                        pull = min(aff, lean) if aff < 0 else lean
                radius = self.hearing_range * (2.0 if pull >= 0 else 1.0)
                falloff = max(0.0, 1.0 - d / radius)
                f = pull * self.attract * falloff
                # personal space: always shove apart when too close to overlap
                if d < self.min_gap:
                    f -= self.repel * (self.min_gap - d) / self.min_gap
                fx += ux * f
                fy += uy * f
                # herd alignment: a nearby soul that is not a foe pulls my heading
                # toward the group's -- keyed on PROXIMITY (a settlement is a herd
                # from tick 0), not on affinity, which barely builds early. Foes
                # (aff < 0) are excluded so two hostile herds don't merge headings.
                if (herd and aff >= 0 and d < self.hearing_range
                        and not (schism and _agree_gate(a, b))):
                    bh = getattr(b, "_heading", None)
                    if bh is not None:
                        wgt = 1.0 - d / self.hearing_range
                        align_x += math.cos(bh) * wgt
                        align_y += math.sin(bh) * wgt
            if guard:
                t = gid.get(getattr(a, "_guard", ""))
                if t is not None and t is not a:
                    gx, gy = t.position[0] - ax, t.position[1] - ay
                    gd = math.hypot(gx, gy) or 1.0
                    if gd > _mating.GUARD_NEAR:   # stand off, never on top
                        fx += gx / gd * _mating.GUARD_PULL
                        fy += gy / gd * _mating.GUARD_PULL
            if herd:
                # the amble: keep a heading, turn it slowly toward the kin average
                # (alignment) with a little wander, and drift forward along it -- a
                # herd roaming the land together instead of jittering in place. The
                # turn is SMALL, so a herd commits to a long straight crossing of the
                # map rather than meandering in one place; it bounces off the walls
                # (below), so the whole map gets travelled corner to corner.
                h = getattr(a, "_heading", None)
                if h is None:
                    h = self._rng.uniform(0.0, 2.0 * math.pi)
                if align_x or align_y:
                    target = math.atan2(align_y, align_x)
                    diff = (target - h + math.pi) % (2.0 * math.pi) - math.pi
                    h += diff * self.herd_align
                h += self._rng.uniform(-1.0, 1.0) * self.herd_turn
                a._heading = h
                fx += math.cos(h) * self.herd_drive
                fy += math.sin(h) * self.herd_drive
            else:
                fx += self._rng.uniform(-1.0, 1.0) * self.wander
                fy += self._rng.uniform(-1.0, 1.0) * self.wander
                if self.bounds is not None:   # gentle pull home so nobody glues to a wall
                    fx += (self.bounds[0] / 2 - ax) * self.center_pull
                    fy += (self.bounds[1] / 2 - ay) * self.center_pull
            # the gait is the STATE walking: restless souls range, the weary drag,
            # children skitter, elders amble
            spd = (0.55 + 0.9 * max(0.0, min(1.0, getattr(a, "arousal", 0.0)))) \
                * (0.45 + 0.55 * max(0.0, min(1.0, a.wellbeing)))
            if self.clock_enabled:
                from world import clock as _clk
                st = _clk.stage(a.age, a.lifespan)
                spd *= 1.25 if st == "child" else (0.55 if st == "elder" else 1.0)
            nx, ny = ax + fx * self.move_step * spd, ay + fy * self.move_step * spd
            if self.bounds is not None:
                bw, bh = self.bounds
                if herd:
                    # bounce the heading off a wall it just reached, so the herd turns
                    # back across the map (full-map roaming) instead of sticking to it
                    hd = a._heading
                    if nx < 0.0 or nx > bw:
                        hd = math.pi - hd
                    if ny < 0.0 or ny > bh:
                        hd = -hd
                    a._heading = hd
                nx = min(max(nx, 0.0), bw)
                ny = min(max(ny, 0.0), bh)
            a.position = (nx, ny)

    # --- decoupled clocks for a live viewer --------------------------------
    # step() bundles everything (incl. the slow LLM turn) and is right for
    # headless/scripted runs. A live viewer instead drives three clocks at
    # their own rates so motion and thought never wait on the model:
    #   animate()    ~30Hz  smooth movement
    #   advance()    ~10Hz  the subconscious heartbeat (memory, thought, urge)
    #   speak_turn()  slow  one LLM turn, the model call OUTSIDE the lock
    def animate(self) -> None:
        """Fast, lock-free: drift bodies one step under social forces."""
        self._drift_positions()

    def advance(self) -> None:
        """The world heartbeat WITHOUT the blocking LLM turn: events, the
        subconscious (memory decay/mutate, thought churn, urge), and reaping."""
        with self.lock:
            self.tick += 1
            if self.events_enabled:
                for ev in self._schedule.get(self.tick, ()):
                    self.inject_event(ev)
            for a in self.agents:
                for ev in a.step(self.tick):
                    self.bus.publish("memory", (a.id, ev))
            if self.stakes_enabled:        # stakes: provisions/actions/hardship
                from world import stakes
                stakes.step(self)
            if self.psyche is not None:    # the workspace: parts bid for the floor
                self.psyche.step(self)
            if self.lore_enabled:          # lore: stories are retold (gossip -> legend)
                from agent import lore
                lore.retell(self)
            self._reap()
            self._process_bardo()    # streams ripen out of the bardo into new lives
            if self.breed_enabled and not self.rebirth_enabled:   # living reproduction
                self._breed()
            if self.murmur_enabled:  # the subconscious mutters and cross-pollinates
                self._murmur()
            self.bus.publish("tick", self.tick)

    def speak_turn(self):
        """One urge-based speech turn. The LLM call runs OUTSIDE the lock so the
        fast animate()/advance() clocks never block on the model. Returns the
        Utterance, or None if nobody had the urge."""
        with self.lock:
            ready = [a for a in self.agents if a.wants_to_speak(self.speak_threshold)]
            if not ready:
                return None
            speaker = max(ready, key=lambda a: a.speak_urge)
            recent = [t for t in self.recent if t][-RECENT_LINES:]
            ctx, addressed, mood = speaker.prepare_speech(recent)
        try:                                   # the slow part, held by no lock
            text = speaker.llm.speak(ctx)
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            # the local model occasionally stalls or times out -- expected and transient on a
            # busy CPU, not a bug. Skip this turn quietly (like a failed reflection) and keep the
            # clocks running; the soul will simply speak a little later.
            print(f"  (… {speaker.name}'s turn skipped: model slow [{type(e).__name__}])", flush=True)
            with self.lock:
                speaker.speak_urge = 0.0
                speaker.cooldown = 3
            return None
        except Exception:  # noqa: BLE001 -- an UNEXPECTED failure: surface it, but still recover
            traceback.print_exc()
            with self.lock:
                speaker.speak_urge = 0.0
                speaker.cooldown = 3
            return None
        with self.lock:
            u = speaker.commit_speech(text, self.tick, addressed, mood)
            self.deliver(u, speaker)
        return u

    def reflect_turn(self):
        """One within-life PRACTICE turn: an eligible soul meets its own mind (the Path, bhāvanā), so
        that step()'s cultivate() then grooves its faculties -- the souls EARN the lean, not only inherit
        it from the bardo tilt. The model call runs OUTSIDE the lock (like speak_turn) so the fast clocks
        never block; the reflection's emotion is its equanimity, read when embeddings are up. Returns the
        reflection text, or None. Picks reflect_enabled souls round-robin."""
        if self.llm is None or not hasattr(self.llm, "generate"):
            return None
        from agent import reflect as _reflect
        with self.lock:
            eligible = [a for a in self.agents if getattr(a, "reflect_enabled", False)]
            if not eligible:
                return None
            a = eligible[self._reflect_i % len(eligible)]
            self._reflect_i += 1
            aid = a.id
            prep = _reflect.prepare(a)              # read-only, under the lock
            if prep is None:
                return None
            prompt, system = prep
        try:                                        # the slow part, held by no lock
            raw = self.llm.generate(prompt, system=system, num_predict=90, temperature=0.7)
        except Exception:  # noqa: BLE001 -- a failed reflection just doesn't happen
            return None
        with self.lock:
            # the soul may have died/been reborn during the slow call -- only write if it still lives
            cur = next((x for x in self.agents if x.id == aid), None)
            if cur is None:
                return None
            text = _reflect.imprint(cur, raw, self.tick)
            # psyche mode: the Watcher's seeing is BROADCAST -- a reflection is the mind
            # observing itself, so it enters EVERY part's memory (the workspace's global
            # availability), not only the reflecting part's own store.
            if (text and self.psyche is not None
                    and getattr(cur, "psyche_faculty", "") == "reflect"):
                emo = next((m.emotion for m in reversed(cur.memory.items)
                            if m.text == text), 0.0)
                for other in self.agents:
                    if other is not cur and getattr(other, "psyche_faculty", ""):
                        other.memory.write(text, tick=self.tick, source="reflection",
                                           speaker_id=cur.id, emotion=emo, weight=0.6)
            return text

    # --- collective consciousness: one mind per faith --------------------------
    # The agents are NEURONS -- they murmur, drift, and cross-pollinate on the
    # cheap. A faith's collective CONSCIOUSNESS is one LLM voice that integrates
    # its neurons' current activity into a single spoken thought. Two faiths ->
    # two minds debating, which is both fast (2 voices, not N) and keeps the war.
    def faith_ids(self) -> list[str]:
        """The faiths currently alive in the realm, in stable order."""
        return list(dict.fromkeys(a.religion for a in self.agents if a.religion))

    def update_camps(self):
        """Emergent mode: recompute the camps from the affinity graph and TAG each
        soul with its camp's banner word (and the largest rival camp's), so its
        speech can lean toward its faction instead of the cluster being invisible
        in what's said. Loners get an empty banner. Returns (camps, banner_by_set)
        for the renderer. Cheap enough to call a few times a second."""
        from services import factions
        with self.lock:
            groups = [g for g in factions.blocs(self.agents) if len(g) > 1]
            banner_map = factions.banners(self.agents)
            by_id = {a.id: a for a in self.agents}
            for a in self.agents:
                a.banner = a.rival_banner = ""
            for g in groups:
                word = banner_map.get(frozenset(g), "")
                rival = next((banner_map.get(frozenset(o), "") for o in groups
                              if o is not g and banner_map.get(frozenset(o))), "")
                for cid in g:
                    if cid in by_id:
                        by_id[cid].banner = word
                        by_id[cid].rival_banner = rival
        return groups, banner_map

    def collective_speak(self, faith_id: str):
        """Gather a faith's neurons' activity, voice it as one integrated thought
        through the LLM (outside the lock), and let the whole realm hear it -- it
        feeds back into its own neurons (top-down) and challenges the rival's."""
        if self.llm is None:
            return None
        with self.lock:
            members = [a for a in self.agents if a.religion == faith_id]
            if not members:
                return None
            faith = RELIGIONS.get(faith_id)
            faith_name = faith.name if faith else faith_id
            # the neural activity: a sample of the members' live drift + recall
            drift, mem = [], []
            for a in members[:8]:
                drift += [d for d in a.thought.current(1) if d]
            for a in members[:6]:
                mem += [m.text for m in a.memory.recall(k=1)]
            mood = sum(a.felt_mood() for a in members) / len(members)
            grace = sum(a.grace for a in members) / len(members)
            rival = next((f for f in self.faith_ids() if f != faith_id), None)
            rival_name = (RELIGIONS[rival].name if rival in RELIGIONS else rival) if rival else None
            proclaim = (self._rng.choice(faith.fundamentals)
                        if faith and faith.fundamentals else None)
            ctx = SpeechContext(
                name=f"the voice of {faith_name}",
                persona=(f"You are the collective consciousness of {faith_name} -- ONE "
                         "mind made of many souls, whose murmuring thoughts surface in "
                         "you as a single voice. Speak for them all, as 'we'."),
                mood=mood,
                drift=drift[-6:],
                memories=[m for m in mem if m][:4],
                belief=faith.creed if faith else members[0].belief,
                reply_to_name=rival_name,
                reply_to_text=self._collective_last.get(rival) if rival else None,
            )
        try:
            text = self.llm.speak(ctx)              # the slow part, no lock held
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None
        with self.lock:
            u = Utterance(speaker_id=f"mind:{faith_id}", text=text, tick=self.tick,
                          source="ai", religion=faith_id, mood=mood,
                          effectiveness=grace, proclamation=(proclaim or ""))
            self._collective_last[faith_id] = text
            # the mind's voice reaches every soul: it reinforces its own neurons
            # and challenges the rival's (driving the war underneath)
            for a in self.agents:
                a.hear(u, self.tick, speaker_name=faith_name)
            self._remember_said(text)
            self.bus.publish("utterance", u)
        return u

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()
