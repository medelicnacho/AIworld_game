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

GEN_SYSTEM = ("You invent vivid, distinct PEOPLE -- each a whole soul with its own "
              "name, history, APPETITES, CONVICTIONS, joys AND wounds. A person with "
              "opinions and desires, who wants things and believes things -- not just "
              "a grieving mood. Write in first person. Avoid clichés of rust, gears, "
              "grey machinery, and do not make every soul defined by loss.")
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
    "Invent ONE person -- the {role} of a small realm, whose life was also shaped "
    "by: {concept}. Give them a real past AND a working life, not just a mood. "
    "Reply in EXACTLY this format and nothing else:\n"
    "NAME: <a single evocative first name, fitting this person>\n"
    "NATURE: <one number from -1.0 (bleak, heavy) to 1.0 (warm, bright)>\n"
    "SELF:\n"
    "<six to eight FIRST-PERSON lines that make a WHOLE, WORKING person: where I "
    "came from, MY CRAFT as the {role} and what I want from it, a BELIEF or opinion "
    "I hold strongly (about my work or the world), what I LOVE, a delight or a "
    "grievance. Concrete and grounded in the trade, not only inner mood. Each line "
    "begins with 'I'. A real person with a job, not a floating sorrow.>")

# A small realm's division of labour. Each role has its own vocabulary and its own
# concerns, so souls talk about DIFFERENT things -- which is what lets factions form
# on interest, and what breaks the "everyone broods on impermanence" sameness. Each
# carries concrete current TASKS, one of which is the soul's pressing business today.
ROLES = [
    ("baker", ["the dawn batch is burning", "the harvest came in thin and the loaves are shrinking",
               "my apprentice ruined the starter again"]),
    ("stonemason", ["racing to finish the west wall before the frost", "a keystone cracked in the night",
                    "the quarry keeps sending soft, treacherous stone"]),
    ("healer", ["fever is creeping through the lower houses", "the herb stores are nearly bare",
                "a birth went wrong before dawn"]),
    ("guard", ["something was at the gate before first light", "the night watch keeps falling asleep",
               "there is talk of raiders on the river road"]),
    ("farmer", ["the rains are late and the field is cracking", "blight is on the eastern rows",
                "the ox went lame at the start of planting"]),
    ("fisher", ["the nets have come up empty three days running", "a storm is building off the water",
                "the boat is taking on water faster than I can bail"]),
    ("smith", ["the forge is down to its last charcoal", "a blade order is owed by market day",
               "the bellows split this morning"]),
    ("weaver", ["the dye lot came out the wrong colour", "a wedding cloak is owed and the loom jammed",
                "good wool is scarce and dear this season"]),
    ("scribe", ["the old records are water-damaged and fading", "a bitter contract dispute waits on my ruling",
                "ink and vellum are running short"]),
    ("brewer", ["the batch soured in the heat", "the festival needs ale and the barley is short",
                "a cask burst in the cellar overnight"]),
    ("shepherd", ["a wolf took two from the flock", "the high pasture is grazed to dirt",
                  "lambing came early and bitterly cold"]),
    ("miller", ["the millstone wants dressing and won't bite", "the stream is too low to turn the wheel",
                "the grain came in damp and is starting to mould"]),
]

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
    conviction: str = ""   # the soul's core stance, to hold and defend in argument
    role: str = ""         # its trade in the realm (concrete, distinct vocabulary)
    task: str = ""         # the pressing business of its day


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
    # the conviction: the soul's strongly-held belief (the line it states one as),
    # which it will hold and defend in argument instead of dissolving into agreement
    conviction = next((l for l in lines if "believ" in l.lower()), lines[0])
    return Character(name=(sanitize(name).capitalize()[:16] or rng.choice(NAMES)),
                     temperament=temp, lines=lines[:8], conviction=conviction)


def generate_character(llm, rng: random.Random | None = None,
                       concept: str | None = None) -> Character:
    """Author one soul via the LLM (or its mock), anchored to `concept` (a random
    preoccupation if none given, which keeps independent souls from converging on
    one aesthetic). Never raises -- a failed call becomes a random fallback."""
    rng = rng or random.Random()
    concept = concept or rng.choice(SEED_CONCEPTS)
    role, tasks = rng.choice(ROLES)        # a trade + a pressing job for the day
    task = rng.choice(tasks)
    try:
        raw = llm.generate(GEN_PROMPT.format(concept=concept, role=role), system=GEN_SYSTEM)
    except Exception:  # noqa: BLE001 -- genesis must never take down the world
        raw = ""
    ch = parse_character(raw, rng)
    ch.role, ch.task = role, task
    return ch


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
    agent.belief = ch.conviction   # the stance it argues from (fed into the prompt)
    agent.role, agent.task = ch.role, ch.task   # its trade and the day's business
    # the story lines are this soul's IDENTITY -- high-salience self-memory, so the
    # subconscious drifts over WHO IT IS and recall_self surfaces it for self-talk
    for ln in ch.lines:
        agent.memory.write(ln, tick=tick, source="self", speaker_id=agent.id, weight=1.4)
    agent.introspect_chance = 0.25   # speaks of itself sometimes, but mostly engages others
    agent.seed_opinion_text(" ".join(ch.lines))   # lexical opinion -> the camp's banner WORD
    # the SIGNED stance that drives bonding: seeded independent of temperament (so
    # factions on it stay emergent, not homophily on disposition), stable per soul.
    agent.seed_stance(random.Random(hash((agent.id, ch.name)) & 0xFFFFFFFF))
