"""The drift monitor (METHODS D1) -- the live runner is a production agent, and
production agents get monitored.

She runs 24/7; the souls now retrain themselves nightly; the register problem is
"managed, not solved". This is the instrument that turns that management into a measured
quantity: a frozen EARLY BASELINE per channel, an online read of the RECENT window, and a
LOUD, DEBOUNCED warning when they part ways. The frozen-world lesson applies to monitors
most of all -- so this one has no bare excepts, no silent states, and its warnings carry
their numbers.

Two kinds of channel:
  numeric  -- any series (reading length, souls alive, deaths/reading): warns when the
              recent mean sits |z| >= z_bar standard errors from the frozen baseline for
              `debounce` consecutive checks (the corroboration rule: one hot check is
              weather, a streak is drift).
  text     -- a voice (hers, the town's): warns when the recent vocabulary has slid away
              from the baseline vocabulary (Jaccard), same debounce.

And the AXIS the register problem has always been about (METHODS D1): movement WITH the
town is wanted (she is supposed to weather); movement toward the GENERIC-ASSISTANT voice
is the failure. `reference_pull()` measures a text channel's slide toward any reference
lexicon; GENERIC_ASSISTANT ships as the reference that matters. Deterministic, stdlib
only; the embedding upgrade rides later without changing the API.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

# the voice this project must never drift into: the helpful-assistant register.
# Lexical v1 (deterministic, testable); an embedding anchor set can replace it later.
GENERIC_ASSISTANT = {
    "certainly", "however", "additionally", "furthermore", "overall", "ultimately",
    "assist", "assistance", "provide", "ensure", "explore", "delve", "insights",
    "perspective", "highlights", "options", "recommend", "solution", "solutions",
    "great", "question", "happy", "help", "glad", "welcome", "absolutely",
    "important", "note", "keep", "mind", "feel", "free", "let", "know",
}


def _words(text: str) -> set[str]:
    return {w.strip(".,!?;:\"'()").lower() for w in text.split()
            if w.strip(".,!?;:\"'()")}


@dataclass
class DriftWarning:
    channel: str
    kind: str          # "numeric" | "vocab" | "pull"
    score: float       # z (numeric) | vocab distance shift | reference pull delta
    detail: str

    def __str__(self) -> str:
        return f"⚠ DRIFT [{self.channel}/{self.kind}] {self.detail}"


class DriftMonitor:
    def __init__(self, baseline_n: int = 60, recent_n: int = 20,
                 z_bar: float = 3.0, vocab_bar: float = 0.35, pull_bar: float = 0.12,
                 debounce: int = 3):
        self.baseline_n, self.recent_n = baseline_n, recent_n
        self.z_bar, self.vocab_bar, self.pull_bar = z_bar, vocab_bar, pull_bar
        self.debounce = debounce
        self._num: dict[str, dict] = {}     # name -> {baseline:[], recent:deque, streak:int}
        self._txt: dict[str, dict] = {}     # name -> {baseline:Counter, base_n, recent:deque,
                                            #          streak:int, pull0:dict, pull_streak:dict}

    # --- feeding --------------------------------------------------------------------------
    def observe(self, name: str, value: float) -> None:
        ch = self._num.setdefault(name, {"baseline": [], "recent": deque(maxlen=self.recent_n),
                                         "streak": 0})
        if len(ch["baseline"]) < self.baseline_n:
            ch["baseline"].append(float(value))    # the early window, frozen once filled
        ch["recent"].append(float(value))

    def observe_text(self, name: str, line: str) -> None:
        ch = self._txt.setdefault(name, {"baseline": Counter(), "base_n": 0,
                                         "recent": deque(maxlen=self.recent_n),
                                         "streak": 0, "pull0": {}, "pull_streak": {}})
        w = _words(line)
        if not w:
            return
        if ch["base_n"] < self.baseline_n:
            ch["baseline"].update(w)
            ch["base_n"] += 1
        ch["recent"].append(w)

    # --- reads ----------------------------------------------------------------------------
    def _vocab_distance(self, ch) -> float | None:
        if ch["base_n"] < self.baseline_n or len(ch["recent"]) < self.recent_n:
            return None                             # still warming up: no verdict, no silence-bug
        base = {w for w, c in ch["baseline"].most_common(200)}
        recent = set().union(*ch["recent"])
        inter = len(base & recent)
        union = len(base | recent) or 1
        return 1.0 - inter / union

    def reference_pull(self, name: str, reference: set[str] = GENERIC_ASSISTANT) -> float | None:
        """How much of the recent vocabulary is the reference lexicon's -- the 'toward the
        generic assistant' axis. Returns the recent share (0..1), or None while warming."""
        ch = self._txt.get(name)
        if ch is None or len(ch["recent"]) < self.recent_n:
            return None
        recent = [w for ws in ch["recent"] for w in ws]
        return sum(1 for w in recent if w in reference) / (len(recent) or 1)

    # --- the check ------------------------------------------------------------------------
    def check(self) -> list[DriftWarning]:
        """Call once per reading. Debounced: a channel must breach its bar `debounce`
        consecutive checks before it warns (one hot check is weather; a streak is drift)."""
        import statistics
        warnings: list[DriftWarning] = []
        for name, ch in self._num.items():
            base = ch["baseline"]
            if len(base) < self.baseline_n or len(ch["recent"]) < self.recent_n:
                continue
            mu = statistics.fmean(base)
            # sd FLOOR: a constant baseline (e.g. a souls-count that never moved during
            # calibration) has sd ~ 0, and dividing by it turns a 1% wobble into
            # z = -223606797 -- numerically true, humanly absurd. The floor says: a
            # channel may never be more certain than 2% of its own level (or 0.05
            # absolute), so a warning's z stays a number a person can read.
            sd = max(statistics.stdev(base), 0.02 * abs(mu), 0.05)
            z = (statistics.fmean(ch["recent"]) - mu) / (sd / (self.recent_n ** 0.5))
            if abs(z) >= self.z_bar:
                ch["streak"] += 1
                if ch["streak"] >= self.debounce:
                    warnings.append(DriftWarning(name, "numeric", z,
                        f"recent mean {statistics.fmean(ch['recent']):.3g} vs baseline "
                        f"{mu:.3g}±{sd:.3g} (z {z:+.1f}, {ch['streak']} checks running)"))
            else:
                ch["streak"] = 0
        for name, ch in self._txt.items():
            d = self._vocab_distance(ch)
            if d is not None and d >= self.vocab_bar:
                ch["streak"] += 1
                if ch["streak"] >= self.debounce:
                    warnings.append(DriftWarning(name, "vocab", d,
                        f"recent vocabulary {d:.0%} away from its baseline "
                        f"({ch['streak']} checks running)"))
            elif d is not None:
                ch["streak"] = 0
            # the generic-assistant axis: warn on a RISE in pull, not its absolute level
            # (a voice may have a little of these words natively; the failure is the slide)
            pull = self.reference_pull(name)
            if pull is not None:
                if name not in ch["pull0"]:
                    ch["pull0"][name] = pull         # first full window = the pull baseline
                delta = pull - ch["pull0"][name]
                if delta >= self.pull_bar:
                    ch["pull_streak"][name] = ch["pull_streak"].get(name, 0) + 1
                    if ch["pull_streak"][name] >= self.debounce:
                        warnings.append(DriftWarning(name, "pull", delta,
                            f"voice sliding toward the generic-assistant register "
                            f"(+{delta:.0%} of recent words, {ch['pull_streak'][name]} "
                            f"checks running)"))
                else:
                    ch["pull_streak"][name] = 0
        return warnings
