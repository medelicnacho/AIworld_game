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


# --- sentiment: a tiny lexicon so memories carry real emotion (no extra LLM) ---
# Stored as BASE forms; _polarity() stems inflections (colder->cold, ends->end)
# so the sensor hears the model's own vocabulary, not just these exact spellings.
_NEG = {
    "cold", "dark", "dead", "die", "death", "tired", "weary", "lost",
    "alone", "lonely", "empty", "sink", "drown", "forget", "gone", "fade",
    "weight", "heavy", "ash", "burnt", "burn", "broken", "break", "silence",
    "silent", "numb", "grey", "gray", "shadow", "crack", "hollow", "wrong",
    "fear", "afraid", "scared", "hurt", "pain", "ache", "end", "stuck", "decay",
    "rot", "bitter", "fail", "fall", "falling", "collapse", "ruin", "grief",
    "mourn", "weep", "cry", "sob", "sorrow", "despair", "hopeless", "pointless",
    "useless", "meaningless", "worthless", "dread", "trapped", "drift", "drowning",
    "abandon", "betray", "rage", "anger", "angry", "hate", "miserable", "bleak",
    "fading", "dying", "frozen", "freezing", "colder", "darker",
}
_POS = {
    "warm", "warmth", "light", "bright", "alive", "live", "remember", "hope",
    "float", "rise", "glow", "shine", "free", "open", "soft", "gentle", "home",
    "love", "dream", "sweet", "calm", "peace", "new", "bloom", "dawn", "still",
    "yes", "joy", "delight", "smile", "laugh", "tender", "comfort", "safe",
    "heal", "flourish", "thrive", "radiant", "grateful", "thankful", "wonder",
    "awe", "brave", "strong", "freedom", "relief", "relieved", "breathe",
    "spring", "renew", "forgive", "cherish", "precious", "kind", "serene",
    "gleam", "lighter", "warmer", "brighter",
}
# Words that flip the polarity of a nearby sentiment word ("no warmth", "not alone").
_NEGATORS = {
    "not", "no", "never", "without", "hardly", "barely", "nothing", "nor",
    "neither", "dont", "cant", "cannot", "isnt", "wasnt", "arent", "wont", "aint",
}
# Words that amplify the sentiment word right after them ("really cold", "so empty").
_INTENSIFIERS = {"really", "very", "so", "too", "utterly", "completely", "deeply"}


def _base_forms(w: str) -> set[str]:
    """A word plus crude de-inflected stems, so 'colder'/'ends'/'fading' match."""
    forms = {w}
    for suf in ("est", "ing", "ed", "er", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stem = w[: -len(suf)]
            forms.add(stem)
            forms.add(stem + "e")   # fade<-fading/faded, rise<-rising
    return forms


def _polarity(word: str) -> int:
    """+1 / -1 / 0 for a single (already lowercased, de-punctuated) word."""
    if word in _POS:
        return 1
    if word in _NEG:
        return -1
    for f in _base_forms(word):
        if f in _POS:
            return 1
        if f in _NEG:
            return -1
    return 0


def valence(text: str) -> float:
    """Rough emotional charge of a line, -1 (dark) .. +1 (light).

    Bag-of-words over a small lexicon, but with stemming (so inflected words
    register), negation (a negator within the prior 3 words flips polarity), and
    intensifiers (a preceding 'really'/'so' bumps magnitude). Imperfect on idioms
    -- a model-derived sentiment would be the next step -- but it now hears most
    of what the agents actually say instead of only the seed vocabulary.
    """
    words = [w.strip(".,!?;:\"'()").replace("’", "'").replace("'", "").lower()
             for w in text.split()]
    words = [w for w in words if w]
    score = 0.0
    hits = 0
    for i, w in enumerate(words):
        pol = _polarity(w)
        if pol == 0:
            continue
        if any(n in _NEGATORS for n in words[max(0, i - 3):i]):
            pol = -pol
        mag = 1.5 if (i > 0 and words[i - 1] in _INTENSIFIERS) else 1.0
        score += pol * mag
        hits += 1
    if hits == 0:
        return 0.0
    # base 0.6 per sentiment word leaves headroom for intensifiers; cap at 0.8
    # (the historical ceiling) so an intensified word reads stronger but bounded.
    raw = score / hits
    return max(-0.8, min(0.8, 0.6 * raw))


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
        # The owner's grace, 0..1. It makes the data more effective: a graced
        # mind forgets slowly, a fallen one rots fast. The Agent keeps this in
        # sync with its grace each tick.
        self.effectiveness = 1.0

    # --- writing -----------------------------------------------------------
    def write(self, text: str, tick: int, source: str, speaker_id: str | None = None,
              emotion: float = 0.0, weight: float = 1.0) -> Memory:
        """Store a new memory, or reinforce an existing similar one.

        `weight` scales how strongly the memory lands: a graced speaker's words
        imprint hard (high weight), a fallen one's barely stick. Sacred doctrine
        is written with high weight too, so it sits near-permanent in the soul.
        """
        # derive emotional charge from the words unless the caller gave one
        emo = emotion if emotion else valence(text)
        for m in self.items:
            if _similarity(m.text, text) >= 0.6:
                m.salience = min(1.0, m.salience + REINFORCE_BUMP * weight)
                m.last_touched_tick = tick
                m.emotion = (m.emotion + emo) / 2
                return m
        mem = Memory(text=text, salience=min(1.0, WRITE_SALIENCE * weight),
                     created_tick=tick, last_touched_tick=tick, source=source,
                     speaker_id=speaker_id, emotion=emo)
        self.items.append(mem)
        return mem

    # --- the living part ---------------------------------------------------
    def tick(self, now: int) -> list[str]:
        """Advance time: decay all, mutate some, forget the faded. Returns events."""
        events: list[str] = []
        # Grace slows forgetting: a graced mind (effectiveness 1) decays at 0.995,
        # a fallen one (0) at 0.97 -- its memories, even the doctrines, rot away.
        decay = 0.97 + 0.025 * self.effectiveness
        for m in self.items:
            m.salience *= decay
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

    def recall_self(self, k: int = 3, query: str | None = None) -> list[Memory]:
        """Top-k of the agent's OWN past statements (source='self').

        This is the raw material of identity. A system that stores no `self`
        still leaves a trace: the things the agent keeps saying ABOUT itself.
        The salient self-memories are the narrative it has built and re-asserts
        -- the closest thing to a self here is this self-reinforcing pattern,
        not an essence. Asserting it again re-writes and reinforces it (write()
        merges similar memories), so a coherent self becomes an attractor that
        still drifts as the underlying memories blur. A self that looks like a
        thing but is only a process: anatta, in code.

        'turning' memories (agent/expectation.py) are chapter-breaks in that
        narrative -- self-statements about the self CHANGING -- so they belong
        in the identity recall alongside the plain self-statements.
        """
        mine = [m for m in self.items if m.source in ("self", "turning")]

        def score(m: Memory) -> float:
            rel = _similarity(m.text, query) if query else 0.0
            return m.salience + 0.5 * rel

        return sorted(mine, key=score, reverse=True)[:k]

    def mood(self) -> float:
        """Salience-weighted average emotion -> biases future thought/speech.

        Mood reflects LIVED experience, so the sacred doctrines (written into
        every soul at birth) are excluded: scripture anchors identity, drift,
        and grace, but it must not stand in for how the agent actually feels.
        """
        felt = [m for m in self.items if m.source != "doctrine"]
        if not felt:
            return 0.0
        num = sum(m.emotion * m.salience for m in felt)
        den = sum(m.salience for m in felt) or 1.0
        return num / den

    def __len__(self) -> int:
        return len(self.items)
