"""Procedural genesis: the LLM authors a unique soul.

Instead of a hand-written cast, each soul is invented at load -- a name, a
disposition, and a body of inner-voice lines that BECOME its Markov subconscious
(the ThoughtLoop drifts over them). Six distinct selves, different every run; and
when a soul is born, a fresh self is minted the same way. Identity is generated,
never authored -- and the factions/ideologies then EMERGE from these random
selves via the opinion dynamics, so nothing about the groups is scripted.

The model is asked for a strict format and the reply is parsed defensively, with
random fallbacks, so a malformed generation can never crash the world.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from services.llm import sanitize

GEN_SYSTEM = ("You invent vivid, distinct PEOPLE -- each a soul with its own name, "
              "past, and inner life: a history, longings, wounds, things it cannot "
              "forget. Write a PERSON with a story, in first person, not a mood or a "
              "landscape. Avoid clichés of rust, gears, and grey machinery.")
# Each soul is anchored to a DIFFERENT preoccupation, sampled without replacement,
# so six independent generations don't all collapse into the same aesthetic.
SEED_CONCEPTS = [
    "the sea and what it swallows", "fire, and what it purifies or destroys",
    "growing things, blossom and rot", "hunger and appetite", "memory and forgetting",
    "war and the quiet after the bodies", "love and its small betrayals",
    "the stars and unbearable distance", "stone, weight, and patience",
    "music, rhythm, and silence", "money, debt, and what a life is worth",
    "the body and its slow decay", "language, naming, and lies",
    "children, lineage, and inheritance", "the hunt, predator and prey",
    "dreams and the dread of waking", "borders, trespass, and belonging",
    "faith and the silence of any god", "the desert, thirst, and mirage",
    "gardens, tending, and what won't grow",
]
GEN_PROMPT = (
    "Invent ONE person -- a soul whose life was shaped by: {concept}. Give them a "
    "real past, not just a mood. Reply in EXACTLY this format and nothing else:\n"
    "NAME: <a single evocative first name, fitting this person>\n"
    "NATURE: <one number from -1.0 (bleak, heavy) to 1.0 (warm, bright)>\n"
    "SELF:\n"
    "<six to eight FIRST-PERSON lines telling who I am: where I came from, a memory "
    "that marked me, someone I lost or love, what I long for, what I fear, what I "
    "cannot forget. Each line begins with 'I'. A person with a story -- not scenery, "
    "not abstraction.>")

NAMES = ["Vesper", "Toll", "Cael", "Mara", "Juno", "Bram", "Sable", "Orin", "Nyx",
         "Pell", "Liri", "Senna", "Corvin", "Dax", "Isolde", "Reyn"]
_THEMES = ["the tide remembers everything", "old stone keeps its silence",
           "grey light at the edge of things", "a slow hunger underneath",
           "dying embers and ash", "deep roots in the dark",
           "the humming of the machine", "salt and rust on the wind",
           "falling snow erases all", "a locked door nobody opens"]


@dataclass
class Character:
    name: str
    temperament: float
    lines: list[str] = field(default_factory=list)


def _find(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def parse_character(raw: str, rng: random.Random) -> Character:
    """Pull a Character out of the model's reply, falling back to random pieces for
    anything missing or malformed."""
    name = _find(r"NAME:\s*(.+)", raw)
    name = name.split()[0].strip(" \"'.,:;-") if name else rng.choice(NAMES)
    nat = _find(r"NATURE:\s*(-?\d*\.?\d+)", raw)
    try:
        temp = max(-1.0, min(1.0, float(nat)))
    except ValueError:
        temp = round(rng.uniform(-1.0, 1.0), 2)
    m = re.search(r"(?:SELF|VOICE):\s*(.*)", raw, re.IGNORECASE | re.DOTALL)
    body = m.group(1) if m else raw
    lines: list[str] = []
    for ln in body.splitlines():
        ln = sanitize(ln).strip(" \t-*").lstrip("0123456789.) ").strip()
        if len(ln) >= 4 and not ln.upper().startswith(("NAME", "NATURE", "VOICE", "SELF")):
            lines.append(ln)
    if not lines:
        lines = rng.sample(_THEMES, 6)
    return Character(name=(sanitize(name).capitalize()[:16] or rng.choice(NAMES)),
                     temperament=temp, lines=lines[:8])


def generate_character(llm, rng: random.Random | None = None,
                       concept: str | None = None) -> Character:
    """Author one soul via the LLM (or its mock), anchored to `concept` (a random
    preoccupation if none given, which keeps independent souls from converging on
    one aesthetic). Never raises -- a failed call becomes a random fallback."""
    rng = rng or random.Random()
    concept = concept or rng.choice(SEED_CONCEPTS)
    try:
        raw = llm.generate(GEN_PROMPT.format(concept=concept), system=GEN_SYSTEM)
    except Exception:  # noqa: BLE001 -- genesis must never take down the world
        raw = ""
    return parse_character(raw, rng)


def dedupe_names(chars: list[Character], rng: random.Random,
                 taken: set[str] | None = None) -> None:
    """The model loves a few names (it keeps picking 'Corvus'); give every soul a
    distinct one, falling back to the name pool when it collides."""
    seen = set(taken or ())
    for ch in chars:
        if ch.name in seen:
            ch.name = next((n for n in NAMES if n not in seen), f"{ch.name}-{len(seen)}")
        seen.add(ch.name)


def seed_agent(agent, ch: Character, tick: int = 0, fresh: bool = False) -> None:
    """Pour a generated soul into an agent: name, disposition, the inner-voice lines
    as BOTH Markov seed phrases AND salient self-memory (so the subconscious drifts
    over them), and the opinion vector that places it in faction-space. `fresh`
    wipes any inherited memory first -- a newborn becoming a genuinely new self."""
    if fresh:
        agent.memory.items.clear()
    agent.name = ch.name
    agent.temperament = ch.temperament
    agent.persona = (f"You are {ch.name}. You have a past and a self of your own. "
                     "Speak from your own memories, story, and longings -- as "
                     "yourself, in the first person, not in abstractions.")
    agent.phrases = list(ch.lines)
    # the story lines are this soul's IDENTITY -- high-salience self-memory, so the
    # subconscious drifts over WHO IT IS and recall_self surfaces it for self-talk
    for ln in ch.lines:
        agent.memory.write(ln, tick=tick, source="self", speaker_id=agent.id, weight=1.4)
    agent.introspect_chance = 0.45   # a generated soul turns to its own story often
    agent.seed_opinion_text(" ".join(ch.lines))
