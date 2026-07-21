"""schema.py -- the attention schema (AST-lite): a mind's model OF ITS OWN attention.

WORKSPACE_NEXT W1 / RESEARCH C1. Graziano's Attention Schema Theory: awareness is not
attention, it is the brain's simplified MODEL of its attention -- a sketch accurate enough
to predict and control the real thing, and wrong in characteristic ways.

This is the honest second attempt at §5.14's one big failed claim. That experiment asked
the FLOOR to forecast the MIND'S MOOD (PREDICTION, 0/5) and it could not: "the floor is a
readout, not a forecaster." The retry does not ask more of the floor. It builds a separate,
much smaller thing whose whole job is to model the floor -- and then asks whether THAT
predicts. Different object, different claim, and the negative result stands either way.

The model is deliberately crude, because AST's claim is that the useful self-model is a
CARICATURE rather than a readout of the machinery:

  presence   a per-part EWMA of floor-share -- "who I have lately been"
  habit      a first-order transition count -- "who tends to follow whom in me"
  guess      from those two: who I expect to hold the floor next
  surprise   the guess was wrong -- "Dread has the floor and I did not see why"

What makes it a SCHEMA and not a log: it never reads the workspace's presence weights or
its fatigue, only the sequence of who actually held the floor. It is a mind watching itself
from the outside, with no access to its own mechanism -- which is also the honest shape of
§5.25's finding, that she tracks valence and never mechanism.

The surprise signal is the load-bearing part. A schema that is never wrong is a mirror, not
a model; the violations are what a self-model is FOR (they mark where the mind has moved
and the picture has not caught up yet).

Gated by World.schema_enabled (default off, THE RULE: nothing changes for a world that
never asks). Pure data -- pickles with the world.
"""
from __future__ import annotations

ALPHA = 0.08          # EWMA rate for presence: slow enough that "who I have been lately"
                      # means a stretch of the stream, not the last few ticks
HABIT_PRIOR = 0.5     # Laplace-ish smoothing on the transition counts, so an unseen
                      # succession is merely unlikely and never impossible
SURPRISE_DECAY = 0.85 # how fast the felt surprise fades once the schema catches up
DWELL_CAP = 8         # reign-length buckets for the hazard: 1,2,..,7,8+ (a reign runs
                      # ~4.4 ticks, so the interesting structure is all in the first few)


class AttentionSchema:
    """A mind's caricature of its own attention. Fed one floor-holder per tick."""

    def __init__(self) -> None:
        self.presence: dict[str, float] = {}          # part -> EWMA floor-share
        self.habit: dict[str, dict[str, float]] = {}  # part -> {successor -> count}, on
                                                      # ACTUAL CHANGES only (the WHERE model)
        self.hazard: dict[tuple, list] = {}           # (part, dwell) -> [changed, stayed]
                                                      # (the WHETHER model)
        self.last: str | None = None                  # who held the floor last tick
        self.dwell: int = 0                           # how long this reign has run
        self.guess: str | None = None                 # who I expect next
        self.surprise: float = 0.0                    # felt wrongness, decaying
        self.seen: int = 0                            # ticks modelled
        self.hits: int = 0                            # guesses that came true
        self.violations: list = []                    # (tick, expected, actual), bounded

    # --- the model, in two questions --------------------------------------------------
    # A single "who comes next" table cannot beat simply saying "the same as now": a reign
    # runs ~4.4 ticks, so persistence is right ~78% of the time and one flat table just
    # learns to say "stay" (measured: 0.771 against persistence's 0.778 -- it had learned
    # THAT the floor persists and nothing about WHERE IT GOES).
    #
    # So the schema asks two questions instead of one:
    #   WHETHER  is this reign about to end? -- keyed on WHO holds the floor and HOW LONG
    #            they have held it. This is the part persistence structurally cannot have:
    #            holding the floor BUILDS fatigue (workspace.py), so the hazard of ending
    #            RISES with dwell, and a reign eight ticks deep is not the same bet as one
    #            that just began.
    #   WHERE    given it ends, who takes it? -- the transition table, over real changes.

    def _hazard_of_ending(self) -> float:
        """P(the floor changes next tick), from this part's dwell. Unseen buckets fall
        back to the part's overall change rate, then to a coin -- a schema always answers."""
        if self.last is None:
            return 0.0
        key = (self.last, min(self.dwell, DWELL_CAP))
        ch, st = self.hazard.get(key, [0.0, 0.0])
        if ch + st >= 3.0:
            return ch / (ch + st)
        tot_ch = sum(v[0] for k, v in self.hazard.items() if k[0] == self.last)
        tot_st = sum(v[1] for k, v in self.hazard.items() if k[0] == self.last)
        return (tot_ch / (tot_ch + tot_st)) if (tot_ch + tot_st) > 0 else 0.5

    def predict(self) -> str | None:
        """Who I expect to hold the floor next: stay unless this reign looks spent, and
        if it looks spent, the habitual successor."""
        if self.last is None:
            return max(self.presence, key=self.presence.get) if self.presence else None
        if self._hazard_of_ending() > 0.5:
            nxt = self.habit.get(self.last)
            if nxt:
                return max(nxt, key=nxt.get)
        return self.last

    def observe(self, floor: str | None, tick: int = 0) -> bool:
        """One tick of watching myself. Returns True when the schema was SURPRISED --
        it had a guess and the guess was wrong. Call once per workspace step, after the
        floor is decided."""
        self.surprise *= SURPRISE_DECAY
        if floor is None:
            return False
        # score the standing guess BEFORE learning from what actually happened, or the
        # schema would be marking its own homework with the answer already in hand
        surprised = False
        if self.guess is not None:
            self.seen += 1
            if self.guess == floor:
                self.hits += 1
            elif self.last != floor:
                # wrong AND the floor genuinely moved -- a real violation, not merely
                # a continuing reign the guess under-called
                surprised = True
                self.surprise = min(1.0, self.surprise + 1.0)
                self.violations.append((tick, self.guess, floor))
                del self.violations[:-200]
        # learn: who I have been, and who follows whom in me
        for pid in set(self.presence) | {floor}:
            hit = 1.0 if pid == floor else 0.0
            self.presence[pid] = (1.0 - ALPHA) * self.presence.get(pid, 0.0) + ALPHA * hit
        # learn BOTH models from this succession
        if self.last is not None:
            changed = self.last != floor
            key = (self.last, min(self.dwell, DWELL_CAP))
            cell = self.hazard.setdefault(key, [0.0, 0.0])
            cell[0 if changed else 1] += 1.0        # WHETHER: did this reign end here
            if changed:                              # WHERE: only real changes teach it
                row = self.habit.setdefault(self.last, {})
                row[floor] = row.get(floor, HABIT_PRIOR) + 1.0
        self.dwell = (self.dwell + 1) if self.last == floor else 1
        self.last = floor
        self.guess = self.predict()
        return surprised

    # --- the read ---------------------------------------------------------------------
    def accuracy(self) -> float | None:
        """How often the guess came true. None until the schema has watched anything --
        no accuracy EXISTS yet, and saying 0.0 would be a lie about a mind with no history
        (the summary() discipline, scripts/stats.py)."""
        return (self.hits / self.seen) if self.seen else None

    def describe(self) -> str:
        """What she can say about her own attention -- the string that feeds the digest.
        The SCHEMA speaks, never the raw log: this is the model's view of itself, caricature
        and all, which is the whole AST claim."""
        if not self.presence:
            return "I have not yet noticed what holds me."
        been = max(self.presence, key=self.presence.get)
        parts = [f"lately I am mostly {been}"]
        if self.guess:
            parts.append(f"I expect {self.guess} next")
        if self.surprise > 0.4 and self.violations:
            _t, expected, actual = self.violations[-1]
            parts.append(f"but {actual} has the floor and I did not see why "
                         f"-- I was watching for {expected}")
        return "; ".join(parts) + "."
