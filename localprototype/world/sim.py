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
from collections import defaultdict

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
        # how much of a strong bond's trust survives the bardo as a faint leaning in
        # the reborn stream (0 = love does not survive death; 0.5 = half, faded)
        self.bond_vasana = 0.5
        self.recent: list[str] = []   # rolling buffer of the last things said
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
        self._reflect_i = 0   # round-robin cursor for reflect_turn (which soul practices next)
        # Guards shared state when a live viewer drives the three clocks
        # (animate / advance / speak_turn) from different threads. The blocking
        # LLM call is the ONE thing kept outside it, so motion never waits.
        self.lock = threading.RLock()
        self._schedule: dict[int, list[WorldEvent]] = defaultdict(list)
        for ev in events or []:
            self._schedule[ev.tick].append(ev)

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

    def step(self) -> None:
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
        # 2) urge-based turn: highest urge over threshold grabs the floor
        ready = [a for a in self.agents if a.wants_to_speak(self.speak_threshold)]
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
        self._reap()
        self._process_bardo()    # streams ripen out of the bardo into new lives
        if self.breed_enabled and not self.rebirth_enabled:   # living reproduction
            self._breed()
        # 2.6) bodies move: drift under social forces so factions take territory.
        if self.move_enabled:
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
                self._dissolve(a)                 # into the bardo; no heir, no author
            elif a.grace >= REPRO_GRACE:
                self._births += 1
                heir = a.reproduce(f"{a.id}.{self._births}")
                survivors.append(heir)            # the heir takes the parent's place
                self.bus.publish("birth", heir.id)
            self.bus.publish("death", a.id)       # the stream, as it was, ends
        self.agents = survivors

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
        })
        self.bus.publish("dissolution", soul.id)

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
        from agent.genesis import NAMES, ROLES, endow_faculties
        from agent import telos as _telos
        if self.llm is None:
            return
        self._births += 1
        living = {a.name for a in self.agents}
        name = next((n for n in self._rng.sample(NAMES, len(NAMES)) if n not in living),
                    f"Stream{self._births}")
        sid = f"stream:{self._births}"
        seeds = entry["seeds"] or ["something stirs in the quiet"]
        a = Agent(sid, name, entry["position"],
                  f"You are {name}, a soul who speaks your own mind.",
                  list(seeds), self.llm, seed=self._rng.randint(0, 10 ** 6),
                  temperament=entry["temperament"],
                  lifespan=entry.get("lifespan", 2000))   # not the default 60!
        a.belief = max(seeds, key=len)   # a nascent stance from the strongest vasana
        role, tasks = self._rng.choice(ROLES)   # a new life, a new trade in the realm
        a.role, a.task = role, self._rng.choice(tasks)
        # the reborn stream wakes a FULL soul (the standard affective endowment -- compassion,
        # ground, joy, prajñā…), with a FRESH aim from its new trade (anatta: the dead soul's
        # project does NOT cross), driven by the carried THIRST -- a clinging death wakes hungry,
        # a wise one at rest. Only the disposition transmigrates; the faculties begin fresh, so no
        # stream is doomed to its predecessor's exact kleśas.
        endow_faculties(a, self._rng)
        a.aim = _telos.fresh_aim(role)
        if self.bodhisattva_wheel:
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
        else:
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
        for a in self.agents:
            ax, ay = a.position
            fx = fy = 0.0
            for b in self.agents:
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
                radius = self.hearing_range * (2.0 if aff >= 0 else 1.0)
                falloff = max(0.0, 1.0 - d / radius)
                f = aff * self.attract * falloff
                # personal space: always shove apart when too close to overlap
                if d < self.min_gap:
                    f -= self.repel * (self.min_gap - d) / self.min_gap
                fx += ux * f
                fy += uy * f
            fx += self._rng.uniform(-1.0, 1.0) * self.wander
            fy += self._rng.uniform(-1.0, 1.0) * self.wander
            if self.bounds is not None:   # gentle pull home so nobody glues to a wall
                fx += (self.bounds[0] / 2 - ax) * self.center_pull
                fy += (self.bounds[1] / 2 - ay) * self.center_pull
            nx, ny = ax + fx * self.move_step, ay + fy * self.move_step
            if self.bounds is not None:
                w, h = self.bounds
                nx = min(max(nx, 0.0), w)
                ny = min(max(ny, 0.0), h)
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
            return _reflect.imprint(cur, raw, self.tick)

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
