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


class AttentionSchema:
    """A mind's caricature of its own attention. Fed one floor-holder per tick."""

    def __init__(self) -> None:
        self.presence: dict[str, float] = {}          # part -> EWMA floor-share
        self.habit: dict[str, dict[str, float]] = {}  # part -> {next part -> count}
        self.last: str | None = None                  # who held the floor last tick
        self.guess: str | None = None                 # who I expect next
        self.surprise: float = 0.0                    # felt wrongness, decaying
        self.seen: int = 0                            # ticks modelled
        self.hits: int = 0                            # guesses that came true
        self.violations: list = []                    # (tick, expected, actual), bounded

    # --- the model ------------------------------------------------------------------
    def predict(self) -> str | None:
        """Who I expect to hold the floor next. Habit first (who follows whom in me),
        falling back to presence (who I have mostly been) when this part has no history
        -- a schema always has an answer, which is what makes it falsifiable."""
        if self.last is not None:
            nxt = self.habit.get(self.last)
            if nxt:
                return max(nxt, key=nxt.get)
        if self.presence:
            return max(self.presence, key=self.presence.get)
        return None

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
        # Record EVERY succession, including a part following itself. The first version
        # recorded only CHANGES and scored 0.13 against a 0.40 base rate -- because a
        # reign lasts ~4.4 ticks, so the floor stays put on 77% of them and a model that
        # can only ever predict a change is wrong nearly every time it opens its mouth.
        # "Who follows whom in me" has to include "and mostly, I go on as I was."
        if self.last is not None:
            row = self.habit.setdefault(self.last, {})
            row[floor] = row.get(floor, HABIT_PRIOR) + 1.0
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
