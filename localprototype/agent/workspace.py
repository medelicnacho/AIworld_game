"""The global workspace -- parts compete for the floor of the mind (PSYCHE.md, step 2).

Baars/Dehaene Global Workspace Theory as an architecture: each tick every part BIDS
(agent/psyche.activation, read off its faculty's live state), the accumulated presence
decides who HAS THE FLOOR, and the winner is what the mind foregrounds -- it gets the
speaking urge (its voice takes the town's floor) and Santāna is told who reigns in her.

The competition follows the §5.13 PRINCIPLE -- selection plus SELF-LIMITING fatigue --
but not the CulturePool's formula. That formula (an instantaneous share penalty) has a
static fixed point under steady bids: measured, a constant loudest bidder ends with the
QUIETEST part holding the floor forever (culture never hits this because motif bids
churn; a mind's bids can be steady for long stretches). So fatigue here has MEMORY --
neuronal adaptation: holding the floor BUILDS fatigue, resting RECOVERS it -- which
oscillates instead of freezing. The fatigue is load-bearing, not decoration: Dread
starts at temperament -0.5 with the grip amplifying every aversive charge, so a bare
argmax would freeze on Dread forever -- exactly the "highest fixed temperament always
wins" cosmetic failure the falsifier (experiment_psyche.py) pre-registers against.
Fatigue is what makes attention TURN OVER: moments, moods, a stream of consciousness
instead of a stuck note.

Couplings (PSYCHE.md step 1 -- each part carries its faculty FOR THE WHOLE MIND):
  * Dread's floor-share is the mind's TENSION: every other part's grip rises with it
    (from its endowed base), so a frightened mind clutches everywhere.
  * Ache's floor-share HOLDS the mind's losses: aversive memories across all parts
    resist decay in proportion to it -- grief persists because Ache is strong.
  * Watcher's reflections are BROADCAST mind-wide (see World.reflect_turn), so the
    mind's seeing of itself enters every part's memory.
  * Longing's wanting has no floor: when its aim is reached, the wanting MOVES to a
    new absence (aim_progress resets) -- the reach never completes, only relocates.

Pure data (pickles with the world); opt-in via World.psyche (default None -- every
existing world, test, and saved snapshot is untouched).
"""

from __future__ import annotations

LOG_CAP = 4000        # dominant-part sequence kept (the falsifier's raw material)
URGE_BUMP = 0.08      # per-tick speaking urge the floor-holder gains (the moment's voice)
TENSION = 0.35        # how hard Dread's floor-share raises the whole mind's grip
ACHE_HOLD = 0.012     # how hard Ache's floor-share holds aversive memory against decay.
                      # Deliberately BELOW the memory decay rate (~1.5%/tick): Ache slows
                      # forgetting, it must never cancel it -- at 0.03 the falsifier caught
                      # grief accumulating without bound and Ache's own bid feeding on it


class Workspace:
    def __init__(self, decay: float = 0.80, fatigue_rate: float = 0.06,
                 fatigue_recover: float = 0.95, margin: float = 1.25) -> None:
        self.w: dict[str, float] = {}      # part id -> accumulated presence (leaky bids)
        self.f: dict[str, float] = {}      # part id -> fatigue [0,1): builds on the floor
        self.names: dict[str, str] = {}    # part id -> name (for logs / the digest)
        self.log: list[str] = []           # winner NAME per tick, bounded
        self._floor: str | None = None     # who HOLDS the floor (stable state, not argmax)
        self.schema = None                 # AttentionSchema when World.schema_enabled --
                                           # the mind's model OF this competition (W1/C1)
        self.decay = decay                 # short memory: a moment is ticks, not eras
        self.fatigue_rate = fatigue_rate       # how fast holding the floor wears you out
        self.fatigue_recover = fatigue_recover  # how fast resting restores you
        self.margin = margin               # hysteresis: a challenger must EXCEED the
                                           # incumbent by this factor to take the floor --
                                           # without it the boundary flickers every tick
                                           # (moments must last ticks, not alternate)

    # --- the competition (selection + self-limiting fatigue-with-memory) -------------
    def observe(self, acts: dict[str, float]) -> None:
        """One round of bidding: normalized activations accrue as leaky presence
        (selection); the floor-holder's fatigue BUILDS while everyone else's RECOVERS
        (self-limiting), so even a steadily-loudest part must eventually yield the
        floor -- and gets it back once rested. Dwell times of a handful of ticks:
        moments, not a frozen note."""
        mx = max(acts.values(), default=0.0)
        for pid, a in acts.items():
            self.w[pid] = self.decay * self.w.get(pid, 0.0) + (a / mx if mx > 0 else 0.0)
            if self.w[pid] < 1e-4:
                del self.w[pid]
        for k in list(self.w):     # a part that stopped bidding (died) fades out
            if k not in acts:
                self.w[k] *= self.decay
                if self.w[k] < 1e-4:
                    del self.w[k]
        # the floor changes hands only when a challenger clearly OUT-PRESSES the
        # fatigued incumbent (hysteresis) -- then the holder tires, the rest recover
        if self._floor not in self.w:
            self._floor = None
        challenger = max(self.w, key=self._effective) if self.w else None
        if challenger is not None and (
                self._floor is None
                or self._effective(challenger) > self.margin * self._effective(self._floor)):
            self._floor = challenger
        for k in list(self.f):
            if k != self._floor:
                self.f[k] *= self.fatigue_recover
                if self.f[k] < 1e-4:
                    del self.f[k]
        if self._floor is not None:
            cur = self.f.get(self._floor, 0.0)
            self.f[self._floor] = cur + self.fatigue_rate * (1.0 - cur)

    def _effective(self, pid: str) -> float:
        return self.w.get(pid, 0.0) * (1.0 - self.f.get(pid, 0.0))

    def reigning_id(self) -> str | None:
        return self._floor

    def reigning(self) -> str | None:
        """The NAME of the part that has the floor (for the digest / display)."""
        rid = self.reigning_id()
        return self.names.get(rid, rid) if rid else None

    def coalition(self, top: int = 2) -> list[str]:
        """The top parts by effective presence -- a recurring pair is a MOOD (Dread+Ache
        = a grief-spiral; Tending+Ember = resilience)."""
        ids = sorted(self.w, key=self._effective, reverse=True)[:top]
        return [self.names.get(i, i) for i in ids]

    def share_of(self, pid: str) -> float:
        tot = sum(self.w.values()) or 1.0
        return self.w.get(pid, 0.0) / tot

    # --- one mind-tick: bid, win the floor, couple the faculties --------------------
    def step(self, world) -> None:
        """Run one workspace round over the world's parts. Called by World.step/advance
        when World.psyche is set; a no-op in any world without parts."""
        parts = [a for a in world.agents if getattr(a, "psyche_faculty", "")]
        if not parts:
            return
        from agent import psyche as _psyche
        self.names = {a.id: a.name for a in parts}
        self.observe({a.id: _psyche.activation(a, parts, now=world.tick) for a in parts})
        rid = self.reigning_id()
        if rid is None:
            return
        self.log.append(self.names.get(rid, rid))
        del self.log[:-LOG_CAP]
        # the attention schema (W1/C1): the mind's MODEL of its own attention, fed the
        # floor-holder and nothing else -- never the presence weights or the fatigue, so
        # it watches itself from outside its own mechanism. Off unless the world asks.
        if getattr(world, "schema_enabled", False):
            if self.schema is None:
                from agent.schema import AttentionSchema
                self.schema = AttentionSchema()
            self.schema.observe(self.names.get(rid, rid), tick=world.tick)
        by_id = {a.id: a for a in parts}
        winner = by_id.get(rid)
        if winner is not None:
            winner.speak_urge += URGE_BUMP     # the floor-holder is the moment's voice

        # coupling 1: Dread's presence is the MIND's tension -- everyone clutches with it
        dread = next((a for a in parts if a.psyche_faculty == "grip"), None)
        if dread is not None:
            tension = self.share_of(dread.id)
            for p in parts:
                if p is not dread:
                    base = getattr(p, "_psyche_base_grip", p.grip)
                    p.grip = min(1.0, base + TENSION * tension)

        # coupling 2: Ache's presence HOLDS the mind's losses against forgetting --
        # the same loss-ledger it reads (what the world did), not the mind's own mutter
        ache = next((a for a in parts if a.psyche_faculty == "salience"), None)
        if ache is not None:
            hold = ACHE_HOLD * self.share_of(ache.id)
            if hold > 0.0:
                for p in parts:
                    for m in p.memory.items:
                        if m.source == "event" and m.emotion < 0.0:
                            m.salience = min(1.0, m.salience * (1.0 + hold))

        # Longing's wanting has no floor: a reached aim only relocates the reach
        for p in parts:
            if p.psyche_faculty == "telos" and getattr(p, "aim_progress", 0.0) >= 1.0:
                p.aim_progress = 0.0
                p.memory.write("the wanted thing arrived, and the wanting moved on",
                               tick=world.tick, source="self", speaker_id=p.id,
                               emotion=-0.1, weight=0.7)
