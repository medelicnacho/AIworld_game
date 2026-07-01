"""CulturePool -- memetic selection + self-limiting fitness for the living voice (FINDINGS §5.13).

The validated emergence recipe, ported to the real town. The unit is a MOTIF (a recurring n-gram),
not a whole line -- so it survives the Markov's recombination (whole lines rarely repeat verbatim, but
"the craving for happiness" or "souls gone from me" recur across many recombinations).

  - SELECTION (echo-weighting): motifs the town keeps speaking gain weight.
  - SELF-LIMITING (motif-fatigue): the reigning motif's fitness FALLS as it dominates (negative
    frequency-dependence), so the culture keeps TURNING OVER -- shifting eras, not a frozen slogan.

Feed it the town's recent speech each reading (`observe`); ask it to re-weight the source phrases the
Markov builds from (`voiced`) so the voice dwells on the reigning motif, then moves on. §5.13 showed
this beats both no-selection (noise) and pure selection (a dead monoculture)."""
from __future__ import annotations

import random


def _canon(s: str) -> str:
    return " ".join(str(s).lower().split()).strip()


# pure function words -- a motif made only of these ("and the", "in the") is not a MOTIF, just glue.
_STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for", "with", "is",
         "are", "was", "were", "be", "it", "its", "my", "your", "his", "her", "their", "i", "you",
         "he", "she", "we", "they", "this", "that", "not", "no", "so", "as", "by", "from", "up",
         "out", "down", "will", "has", "have", "had", "now", "again", "then", "there", "keeps"}


class CulturePool:
    def __init__(self, n: int = 3, decay: float = 0.85, fatigue: float = 3.4,
                 cap: int = 80, echo: int = 2, seed: int | None = None) -> None:
        self.mw: dict[str, float] = {}     # motif (n-gram) -> cultural weight
        self.n = n                         # bigrams recur across recombinations; trigrams flood
        self.decay = decay
        self.fatigue = fatigue             # >0 -> self-limiting (the reigning motif wears out)
        self.cap = cap                     # small -> weight concentrates instead of spreading thin
        self.echo = echo                   # a motif must recur across >=echo lines to gain weight
        self._rng = random.Random(seed)

    def _motifs(self, line: str) -> list[str]:
        toks = _canon(line).split()
        if len(toks) < self.n:
            return []
        out = []
        for i in range(len(toks) - self.n + 1):
            gram = toks[i:i + self.n]
            if any(t not in _STOP for t in gram):    # skip all-glue motifs ("and the", "in the")
                out.append(" ".join(gram))
        return out

    def observe(self, lines) -> None:
        """The town spoke -- ECHOED motifs gain weight (selection), then decay + the reigning motif
        wears out (self-limiting). The echo threshold filters one-off recombination noise, so only
        motifs the town actually keeps repeating concentrate."""
        counts: dict[str, int] = {}
        for ln in lines:
            for mo in set(self._motifs(ln)):     # per-line: don't over-count a motif within one line
                counts[mo] = counts.get(mo, 0) + 1
        for mo, c in counts.items():
            if c >= self.echo:                    # SELECTION: only motifs echoed across >=echo lines
                self.mw[mo] = self.mw.get(mo, 0.0) + c
        tot = sum(self.mw.values()) or 1.0
        for k in list(self.mw):
            p = self.mw[k] / tot
            self.mw[k] *= self.decay * max(0.04, 1.0 - self.fatigue * p)   # decay + SELF-LIMITING fatigue
            if self.mw[k] < 1e-2:
                del self.mw[k]
        if len(self.mw) > self.cap:
            for k in sorted(self.mw, key=self.mw.get)[:len(self.mw) - self.cap]:
                del self.mw[k]

    def weight_of(self, line: str) -> float:
        ms = self._motifs(line)
        return max((self.mw.get(m, 0.0) for m in ms), default=0.0)

    def voiced(self, sources) -> list[str]:
        """Re-weight the source phrases: lines carrying the reigning motif get amplified (up to 8x),
        so the Markov dwells on the current era; when the motif fatigues, its lines fall back."""
        srcs = [s for s in sources if s and s.strip()]
        if not self.mw or not srcs:
            return srcs
        ws = [self.weight_of(s) for s in srcs]
        mx = max(ws) or 1.0
        out: list[str] = []
        for s, w in zip(srcs, ws):
            out += [s] * max(1, round(8 * w / mx))
        return out

    def reigning(self) -> str | None:
        return max(self.mw, key=self.mw.get) if self.mw else None

    def era(self, top: int = 3) -> list[str]:
        return [k for k, _ in sorted(self.mw.items(), key=lambda kv: -kv[1])[:top]]
