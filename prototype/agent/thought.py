"""The subconscious: a Markov drift over the agent's own memory.

Runs every tick, cheaply. It builds an order-1 chain from the agent's memories
(transition weights biased by salience, so charged memories dominate the drift)
plus a few persona seed phrases, then walks it to produce short dreamlike
fragments. These fragments are what the LLM is later asked to "talk about" -- the
loud, deliberate voice speaking from the quiet, associative one.
"""

from __future__ import annotations

import random
from collections import defaultdict


SEED_WEIGHT = 1.2       # weight of persona phrases vs. lived memory (anchors identity)
MAX_FRAGMENT = 7        # max words in a single drift fragment
BUFFER = 5              # how many recent fragments to keep around


def _words(text: str) -> list[str]:
    return [w for w in (t.strip(".,!?") for t in text.split())
            if w and w != "..."]


class ThoughtLoop:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._starts: list[tuple[str, float]] = []
        self._trans: dict[str, list[tuple[str, float]]] = defaultdict(list)
        self.drift: list[str] = []

    def learn(self, memories, seed_phrases: list[str]) -> None:
        """Rebuild the chain from current memory (weighted by salience) + persona."""
        self._starts.clear()
        self._trans.clear()
        sources = [(p, SEED_WEIGHT) for p in seed_phrases]
        sources += [(m.text, max(0.05, m.salience)) for m in memories]
        for text, weight in sources:
            ws = _words(text)
            if not ws:
                continue
            self._starts.append((ws[0], weight))
            for a, b in zip(ws, ws[1:]):
                self._trans[a.lower()].append((b, weight))

    def step(self) -> str | None:
        """Generate one fragment and push it onto the rolling drift buffer."""
        if not self._starts:
            return None
        word = self._weighted(self._starts)
        out = [word]
        for _ in range(MAX_FRAGMENT - 1):
            nxt = self._trans.get(out[-1].lower())
            if not nxt:
                break
            out.append(self._weighted(nxt))
        fragment = " ".join(out)
        self.drift.append(fragment)
        del self.drift[:-BUFFER]
        return fragment

    def current(self, n: int = 3) -> list[str]:
        return self.drift[-n:]

    def _weighted(self, choices: list[tuple[str, float]]) -> str:
        total = sum(w for _, w in choices)
        r = self._rng.uniform(0, total)
        upto = 0.0
        for item, w in choices:
            upto += w
            if upto >= r:
                return item
        return choices[-1][0]
