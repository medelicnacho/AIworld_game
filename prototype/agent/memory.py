"""The living memory store: write, decay, forget, reinforce, mutate, recall.

This is the heart of the project. Memory both *drives* thought (recall feeds
speech) and is *changed by* what an agent says and hears (write/reinforce/bias).
v1 uses naive text-overlap for similarity; later this becomes embeddings.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


# --- tuning knobs (move to config.yaml later) -------------------------------
DECAY_PER_TICK = 0.985      # salience multiplier each tick -> slow forgetting
FORGET_THRESHOLD = 0.08     # below this salience, a memory is pruned
REINFORCE_BUMP = 0.35       # salience added when a similar memory is re-heard
WRITE_SALIENCE = 0.6        # starting salience of a fresh memory
MUTATE_CHANCE = 0.015       # per-tick chance an old memory mutates its text
MUTATE_MIN_AGE = 20         # only memories older than this (ticks) can mutate
# ---------------------------------------------------------------------------

# Memories don't gain detail as they age -- they lose and blur it. This maps
# specific words to vaguer ones, so a remembered phrase softens over time.
BLUR = {
    "deep": "dark", "cold": "distant", "warmth": "something", "warm": "faint",
    "fire": "light", "smoke": "haze", "water": "current", "river": "water",
    "light": "glow", "wings": "weight", "night": "dark", "downhill": "away",
    "moving": "drifting", "rises": "lifts", "dreamed": "thought",
    "circling": "turning", "heavier": "heavy",
}
_SEP = "..."  # marks where a recalled fragment was woven in; never blur/drop it


def _collapse_dups(text: str) -> str:
    """Safety net: never let two identical words sit adjacent (kills stutter)."""
    out: list[str] = []
    for w in text.split():
        if not out or out[-1].lower() != w.lower():
            out.append(w)
    return " ".join(out)


def _tokens(text: str) -> set[str]:
    return {w.strip(".,!?").lower() for w in text.split() if w.strip(".,!?")}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)  # Jaccard overlap


@dataclass
class Memory:
    text: str
    salience: float
    created_tick: int
    last_touched_tick: int
    source: str = "heard"        # "self" | "heard" | "user"
    speaker_id: str | None = None
    emotion: float = 0.0         # valence -1..1 (placeholder for now)
    mutation_count: int = 0


class MemoryStore:
    def __init__(self, seed: int | None = None) -> None:
        self.items: list[Memory] = []
        self._rng = random.Random(seed)

    # --- writing -----------------------------------------------------------
    def write(self, text: str, tick: int, source: str, speaker_id: str | None = None,
              emotion: float = 0.0) -> Memory:
        """Store a new memory, or reinforce an existing similar one."""
        for m in self.items:
            if _similarity(m.text, text) >= 0.6:
                m.salience = min(1.0, m.salience + REINFORCE_BUMP)
                m.last_touched_tick = tick
                m.emotion = (m.emotion + emotion) / 2
                return m
        mem = Memory(text=text, salience=WRITE_SALIENCE, created_tick=tick,
                     last_touched_tick=tick, source=source, speaker_id=speaker_id,
                     emotion=emotion)
        self.items.append(mem)
        return mem

    # --- the living part ---------------------------------------------------
    def tick(self, now: int) -> list[str]:
        """Advance time: decay all, mutate some, forget the faded. Returns events."""
        events: list[str] = []
        for m in self.items:
            m.salience *= DECAY_PER_TICK
            age = now - m.last_touched_tick
            if age >= MUTATE_MIN_AGE and self._rng.random() < MUTATE_CHANCE:
                before = m.text
                m.text = self._mutate(m.text)
                if m.text != before:
                    m.mutation_count += 1
                    events.append(f"mutated: '{before}' -> '{m.text}'")

        kept, forgotten = [], []
        for m in self.items:
            (kept if m.salience >= FORGET_THRESHOLD else forgotten).append(m)
        self.items = kept
        for m in forgotten:
            events.append(f"forgot: '{m.text}'")
        return events

    def _mutate(self, text: str) -> str:
        """Memories drift by *losing and blurring* detail, never by stuttering.

        One small edit per mutation: drop a word, blur a word to something vaguer,
        or swap adjacent words (misremembered order). Fragment separators ('...')
        are preserved so woven recollections stay legible.
        """
        words = text.split()
        # indices we're allowed to touch (skip separators)
        idx = [i for i, w in enumerate(words) if w != _SEP]
        if len(idx) <= 2:
            return text

        roll = self._rng.random()
        if roll < 0.45:                                  # blur to something vaguer
            blurrable = [i for i in idx if words[i].lower() in BLUR]
            i = self._rng.choice(blurrable) if blurrable else self._rng.choice(idx)
            words[i] = BLUR.get(words[i].lower(), words[i])
            if words[i] == text.split()[i]:              # nothing to blur -> drop
                words.pop(i)
        elif roll < 0.80:                                # forget a word
            words.pop(self._rng.choice(idx))
        else:                                            # misremember word order
            i = self._rng.choice(idx[:-1])
            words[i], words[i + 1] = words[i + 1], words[i]

        return _collapse_dups(" ".join(words))

    # --- recall ------------------------------------------------------------
    def recall(self, k: int = 3, query: str | None = None) -> list[Memory]:
        """Top-k by salience, optionally biased toward relevance to `query`."""
        def score(m: Memory) -> float:
            rel = _similarity(m.text, query) if query else 0.0
            return m.salience + 0.5 * rel
        return sorted(self.items, key=score, reverse=True)[:k]

    def mood(self) -> float:
        """Salience-weighted average emotion -> biases future thought/speech."""
        if not self.items:
            return 0.0
        num = sum(m.emotion * m.salience for m in self.items)
        den = sum(m.salience for m in self.items) or 1.0
        return num / den

    def __len__(self) -> int:
        return len(self.items)
