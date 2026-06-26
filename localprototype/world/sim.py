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
        self._bardo.append({
            "seeds": seeds,
            "belief_vec": list(soul.belief_vec) if soul.belief_vec is not None else None,
            "temperament": max(-1.0, min(1.0, soul.temperament + self._rng.uniform(-0.25, 0.25))),
            "position": soul.position,
            "countdown": self._rng.randint(*BARDO_TICKS),
            "lifespan": soul.lifespan,   # the new stream lives on the lineage's scale
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
        from agent.genesis import NAMES
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
        for frag in seeds:
            a.memory.write(frag, tick=self.tick, source="self", speaker_id=sid, weight=0.8)
        if entry["belief_vec"] is not None:
            # gentle perturbation: the lean PERSISTS, softened by the dissolution
            # (small per-component noise -- in a high-dim space even this spreads)
            noise = [self._rng.gauss(0.0, 0.06) for _ in entry["belief_vec"]]
            a.belief_vec = _normalize([v + n for v, n in zip(entry["belief_vec"], noise)])
            a.belief_grounded = True
        a.introspect_chance = 0.45
        self.agents.append(a)
        self.bus.publish("rebirth", sid)

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
        except Exception:  # noqa: BLE001 -- contain a bad turn, keep the clocks running
            traceback.print_exc()
            with self.lock:
                speaker.speak_urge = 0.0
                speaker.cooldown = 3
            return None
        with self.lock:
            u = speaker.commit_speech(text, self.tick, addressed, mood)
            self.deliver(u, speaker)
        return u

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
