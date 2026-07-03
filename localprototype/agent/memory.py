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
    lore_id: str = ""            # provenance: the event this memory descends from, carried
                                 # through retellings (agent/lore.py) -- ground truth for
                                 # tracing a LEGEND back to what actually happened. The text
                                 # mutates; the tag does not. "" = not a story.
    alien_merges: int = 0        # provenance (C14): how often a telling from a DIFFERENT
                                 # source merged into this memory -- each blend smears the
                                 # frame ("did I live this or hear it?"). Ground truth for
                                 # source-confusion; never decays, unlike the felt attribution.
    mineness: float = 1.0        # ownership (S2, Strawson's I*): whether the remembered
                                 # experience presents as MINE -- separable from content,
                                 # accuracy, and provenance. 1 = owned autobiography;
                                 # < 0.5 = known-but-unowned ("this happened -- but not,
                                 # I think, to me"). The wheel's carried residue is exactly
                                 # unowned experience.


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
              emotion: float = 0.0, weight: float = 1.0, lore_id: str = "",
              mineness: float = 1.0) -> Memory:
        """Store a new memory, or reinforce an existing similar one.

        `weight` scales how strongly the memory lands: a graced speaker's words
        imprint hard (high weight), a fallen one's barely stick. Sacred doctrine
        is written with high weight too, so it sits near-permanent in the soul.
        `lore_id` carries provenance (which event a retold story descends from);
        a merge inherits it if the resident copy has none.
        `mineness` (S2) marks whether the experience presents as OWNED; carried
        residue from the wheel is written unowned (< 0.5).
        """
        # derive emotional charge from the words unless the caller gave one
        emo = emotion if emotion else valence(text)
        for m in self.items:
            if _similarity(m.text, text) >= 0.6:
                m.salience = min(1.0, m.salience + REINFORCE_BUMP * weight)
                m.last_touched_tick = tick
                m.emotion = (m.emotion + emo) / 2
                if source != getattr(m, "source", source):
                    # a telling from a DIFFERENT source blended in: the words merged, and the
                    # FRAME smeared with them ("did I live this, or hear it?"). This counter is
                    # the ground truth source-confusion (C14) grows from -- retelling a story
                    # in your own voice is precisely how it becomes yours.
                    m.alien_merges = getattr(m, "alien_merges", 0) + 1
                if lore_id and not getattr(m, "lore_id", ""):
                    m.lore_id = lore_id
                elif lore_id and getattr(m, "lore_id", "") == lore_id:
                    # communal error-correction (oral tradition): a NOTICEABLY fuller telling
                    # of the same story displaces my more-decayed version. The >=2-word margin
                    # is load-bearing, both failure modes measured: repair on ANY longer
                    # telling freezes the legend verbatim (path-dependence dies); no repair
                    # and ~half the runs decay to untraceable mush. Single-word losses, blur,
                    # and reorder still drift -- catastrophic loss gets caught.
                    if len(text.split()) >= len(m.text.split()) + 2:
                        m.text = text
                return m
        mem = Memory(text=text, salience=min(1.0, WRITE_SALIENCE * weight),
                     created_tick=tick, last_touched_tick=tick, source=source,
                     speaker_id=speaker_id, emotion=emo, lore_id=lore_id,
                     mineness=mineness)
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

        UNOWNED memories (S2: mineness < 0.5) are excluded: what one cannot claim
        cannot be raw material for one's story -- though its charge still moves
        mood() below. That gap IS the behaviour/report dissociation S2 predicts:
        shaped by what it cannot tell.
        """
        mine = [m for m in self.items if m.source in ("self", "turning")
                and getattr(m, "mineness", 1.0) >= 0.5]

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


def hedged(m: Memory) -> str:
    """The memory's text, carrying EARNED doubt (C2, metamemory): mutation_count is the
    substrate's ground-truth record of how often this memory has blurred -- until now tracked
    and never read by any self. A self that says 'I may have it wrong' exactly when it does is
    quiet, deep realism -- and by construction honest, since the hedge IS the drift counter
    speaking. Used at PROMPT time only; the stored text is never altered."""
    if m.mutation_count >= 3:
        return f"{m.text} (though that memory has worn, and I may have it wrong)"
    if m.mutation_count >= 1:
        return f"{m.text} (as best I remember)"
    return m.text


# --- C14: the source discriminator (Lau's perceptual reality monitoring) ---------------------
# Every item always carried provenance no self ever read (source, lore_id, drift counters).
# source_tag() is the DISCRIMINATOR that reads it at recall -- and, crucially, it reads it
# through the drift: attribution is a FEELING about a memory, and it wears out with the words.
# The pristine `source`/`lore_id` fields never decay (they are the experimenter's ground
# truth); what decays is the self's ACCESS to them. That gap is where source-confusion lives:
# a story mutated and retold enough presents as simply KNOWN -- believed-as-lived -- while
# lore_id still remembers what it really was. Emergent false memory, auditable end-to-end.

_MINE_SOURCES = ("self", "talk", "reflection", "turning")


def attribution_strength(m: Memory) -> float:
    """How firmly this memory's FRAME (where it came from) still holds.

    Two wearing forces, deliberately UNEQUAL: a cross-source merge (0.9 each) smears the
    frame directly -- retelling a story in your own voice is how it becomes yours -- while
    a text mutation (0.2 each) wears it only slowly. Content doubt and source doubt are
    DIFFERENT axes: C2's hedge tier ("worn, may have it wrong" at 3 mutations) fires long
    before the frame frays (~8 pure mutations), so a worn witnessed event doubts its WORDS
    without disclaiming its LIFE. v1 weighted mutations 0.35 and conflated the two -- caught
    by the existing C2 test, rebalanced, and the held-out verdict re-run on fresh seeds."""
    return 1.0 / (1.0 + 0.2 * getattr(m, "mutation_count", 0)
                  + 0.9 * getattr(m, "alien_merges", 0))


def source_tag(m: Memory) -> str:
    """The discriminator's verdict at recall: 'dream' | 'story' | 'mine' | 'witnessed' |
    'doctrine' | 'unsure'. NOT a lookup of the source field -- a read of it THROUGH the
    drift, so it can honestly err (C14's falsifier (b) measures exactly those errors)."""
    src = getattr(m, "source", "heard")
    if src == "doctrine":
        return "doctrine"                       # scripture never loses its frame
    s = attribution_strength(m)
    if s < 0.3:
        # the frame is gone entirely: whatever this was, it now presents as one's own --
        # the confident false memory (a legend worn until it reads as lived life)
        return "mine"
    if s < 0.5:
        return "unsure"                         # the honest middle: "did I live this?"
    if src == "dream":
        return "dream"
    if src == "lore" or (getattr(m, "lore_id", "") and src == "heard"):
        return "story"                          # a telling, received -- not lived
    if src in _MINE_SOURCES:
        return "mine"
    return "witnessed"                          # heard / user / event / ai: lived perception


def attributed(m: Memory) -> str:
    """The full provenance voice-gate (C2 confidence + C14 source + S2 ownership), at PROMPT
    time only -- the stored text is never altered. Dreams speak as dreams, stories as stories,
    a lost frame confesses itself, an unowned memory declines the autobiography."""
    if getattr(m, "mineness", 1.0) < 0.5:
        return f"{m.text} (this happened -- though not, I think, to me)"
    tag = source_tag(m)
    if tag == "dream":
        return f"{m.text} (I dreamt it, I think)"
    if tag == "story":
        return f"{m.text} (a story I was told)"
    if tag == "unsure":
        return f"{m.text} (I no longer know if I lived this or was only told it)"
    return hedged(m)                            # mine / witnessed / doctrine: C2's drift hedge
