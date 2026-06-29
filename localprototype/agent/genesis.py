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

GEN_SYSTEM = ("You invent vivid, distinct, ORDINARY PEOPLE -- working folk of a small "
              "town, each with a name, a trade, appetites, opinions, small joys and "
              "gripes, and neighbours they like and dislike. Real people talking about "
              "real daily life -- their work, their family, the market, the weather, who "
              "owes whom, who they're sweet on -- NOT philosophers. Write in first "
              "person, plain everyday speech. AVOID grand or cosmic themes; avoid talk of "
              "the void, meaning, eternity, the soul, or the slow dissolution of the "
              "self. Keep it concrete and human. Do not make them sad or defined by loss "
              "-- most people are just getting on with their day.")
# Each soul is anchored to a DIFFERENT everyday preoccupation, sampled without
# replacement, so independent generations diverge -- and stay GROUNDED in ordinary
# working life rather than collapsing into existential brooding.
SEED_CONCEPTS = [
    "pride in a craft done better than anyone else's", "a rivalry with another tradesperson",
    "a debt being slowly worked off", "courting someone, or an unspoken crush",
    "a stubborn animal or tool that won't cooperate", "feeding a family through a lean season",
    "a feud with a neighbour over a boundary or a fence", "ambition to grow the business and earn a name",
    "the festival or market day they're nervously preparing for", "a recipe or technique they're perfecting",
    "raising a child or a clumsy apprentice", "a small vice -- drink, gambling, gossip, sweets",
    "saving up for something specific (a boat, a roof, a ring)", "what the neighbours think of them",
    "a friendship that's drifting, or mending", "wanting to be better at the trade than their parent was",
    "a long-running joke or grudge in the town", "the weather wrecking or blessing the work",
    "a deal that went sour at market", "homesickness, or itching to see another town",
]
GEN_PROMPT = (
    "Invent ONE ordinary person -- the {role} of a small town -- whose life right now "
    "turns around: {concept}. Reply in EXACTLY this format and nothing else:\n"
    "NAME: <a single plain first name>\n"
    "NATURE: <one number from -1.0 to 1.0; most ordinary people sit around 0 to 0.6, "
    "not bleak>\n"
    "AIM: <one concrete thing you are working toward in your craft this season -- a "
    "project you tend and want to see come good, e.g. 'brew an ale worth the festival' "
    "or 'raise the west wall before the frost'>\n"
    "SELF:\n"
    "<six to eight FIRST-PERSON lines of a real working person: what I do each day as "
    "the {role}; who I deal with (name a neighbour, a rival, a child); what I WANT this "
    "season; a strong opinion I firmly believe about my work or how things should be "
    "done; one small JOY and one small GRIPE. Concrete and everyday -- the bread, the "
    "wall, the goat, the debt, the festival -- NOT inner mood or grand statements. Each "
    "line begins with 'I'. A neighbour you could chat with over a fence, not a poet "
    "brooding on existence.>")

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

# A coined name from nothing -- syllables assembled to order, not drawn from a fixed
# cast. The rebirth wheel uses this so a stream that dissolves does not come back wearing
# the same handful of names: each new soul is a name never heard before and, once gone,
# effectively never returns (the space is ~thousands). Phonotactics alternate consonant
# and vowel so the coinage is pronounceable but storyless -- fitting a "merely designated"
# name (see World._coalesce). NAMES above stays the hand-authored founding cast.
_ONSET  = ["b", "br", "c", "cl", "cr", "d", "dr", "f", "fr", "g", "gr", "h", "j", "k",
           "l", "m", "n", "p", "ph", "pr", "r", "s", "sh", "sl", "st", "t", "th", "tr",
           "v", "vr", "w", "z", "", "", "", ""]      # "" -> vowel-initial (Orin, Isolde)
_VOWEL1 = ["a", "e", "i", "o", "u", "y", "ae", "ei", "ia", "io"]   # syllable 1 may diphthong
_VOWEL2 = ["a", "e", "i", "o", "u", "y"]                           # syllable 2 stays simple
_MID_1  = ["b", "c", "d", "g", "l", "m", "n", "r", "s", "t", "v", "th"]            # single
_MID_2  = _MID_1 + ["ll", "nd", "st", "rn", "ss", "sh", "ld", "br", "dr", "ndr"]   # + clusters
_CODA   = ["n", "r", "l", "s", "th", "ll", "rn", "m", "nd", "", ""]
_SUFFIX = ["wyn", "wen", "dor", "ric", "ven", "ner", "lis", "mir", "reth", "dris",
           "wel", "gar", "sa", "ra", "na", "da", "la"]      # name-like, consonant-initial


def coined_name(rng: random.Random, taken=()) -> str:
    """Assemble a fresh, never-before-heard first name. Avoids any name in `taken`."""
    taken = set(taken)
    for _ in range(40):
        onset = rng.choice(_ONSET)
        name = onset + rng.choice(_VOWEL1)
        if rng.random() < 0.62:                          # a second syllable
            # don't stack two consonant clusters -> keep it pronounceable
            mid = _MID_1 if len(onset) > 1 else _MID_2
            name += rng.choice(mid) + rng.choice(_VOWEL2)
        r = rng.random()
        if r < 0.45:
            name += rng.choice(_CODA)
        elif r < 0.72:
            name += rng.choice(_SUFFIX)
        # else: end on the open vowel (Mara, Liri, Senna)
        name = name.capitalize()
        if 3 <= len(name) <= 9 and name not in taken:
            return name
    return f"Stream-{rng.randint(1000, 9999)}"            # vanishingly rare fallback
_THEMES = ["the morning bread and who's late for it", "the price of wool this season",
           "my neighbour's noisy geese again", "saving up for a better roof",
           "the festival coming up fast", "my apprentice's clumsy hands",
           "a good haggle at the market", "the cart wheel I keep mending",
           "my mother's old recipe", "the long walk to the well"]


@dataclass
class Character:
    name: str
    temperament: float
    lines: list[str] = field(default_factory=list)
    conviction: str = ""   # the soul's core stance, to hold and defend in argument
    role: str = ""         # its trade in the realm (concrete, distinct vocabulary)
    task: str = ""         # the pressing business of its day
    aim: str = ""          # telos/chanda: a concrete craft goal it tends and is drawn toward


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
    # the aim: a concrete craft goal it is drawn toward (telos/chanda). Fall back to a
    # "what I want" line, else a plain role-shaped goal, so every soul has a future to tend.
    aim = _find(r"AIM:\s*(.+)", raw)
    if not aim:
        aim = next((l for l in lines if any(w in l.lower() for w in ("want", "hope", "save", "finish"))), "")
    aim = sanitize(aim).strip(" \"'.,:;-")[:80]
    return Character(name=(sanitize(name).capitalize()[:16] or rng.choice(NAMES)),
                     temperament=temp, lines=lines[:8], conviction=conviction, aim=aim)


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
    if not ch.aim:
        ch.aim = f"make my work as the {role} come good this season"
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


def endow_faculties(agent, rng) -> None:
    """The standard affective endowment every soul wakes with -- the brahmavihāras (metta/karuṇā via
    compassion+bodhicitta, muditā via joy), the buddha-nature ground, the Mahāyāna/Vajrayāna faculties
    (prajñā, transmutation, self-liberation), a MODEST VARIED grip (the friction a self loosens), and
    a telos (a future to tend). Shared by genesis (authored souls) AND rebirth (reborn streams), so a
    new stream wakes a FULL soul rather than a blank one. Caller may override any dial afterwards
    (an archetype, or a reborn stream's carried thirst)."""
    agent.compassion = 0.6           # meet others with warmth (metta), hold views without contempt
    agent.ground_enabled = True      # buddha-nature: rest in basic goodness, veiled only by clinging
    agent.bodhicitta = 0.5           # compassion as an aim: proactively turn toward and ease suffering
    agent.prajna = 0.4               # some wisdom: hold self/grievances lightly as empty configurations
    # a modest, varied baseline of clinging -- with none the world rests pre-purified, with too much
    # it re-darkens; loosened by prajna (effective = grip*(1-prajna)) and veiled-warmth restored by ground
    agent.grip = rng.uniform(0.2, 0.5)
    agent.transmute = 0.4            # Vajrayāna: meet a charge and turn it to clarity, not only release it
    agent.self_liberation = 0.4      # Vajrayāna rang drol: let a charge free itself as it arises
    agent.joy = 0.5                  # muditā/pīti: savour the good and rejoice with others (not anhedonia)
    agent.telos = 0.5                # chanda: tend an aim and be drawn toward it (savoured/craved per faculties)


def seed_agent(agent, ch: Character, tick: int = 0, fresh: bool = False,
               archetype=None) -> None:
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
    agent.aim = ch.aim             # telos/chanda: a craft goal it tends and is drawn toward (a future)
    # the story lines are this soul's IDENTITY -- high-salience self-memory, so the
    # subconscious drifts over WHO IT IS and recall_self surfaces it for self-talk
    for ln in ch.lines:
        agent.memory.write(ln, tick=tick, source="self", speaker_id=agent.id, weight=1.4)
    agent.introspect_chance = 0.25   # speaks of itself sometimes, but mostly engages others
    agent.bond_enabled = True        # form dyadic bonds toward other souls (relate, not just cluster)
    agent.self_model_enabled = True  # consolidate a self-model and speak from it (perpetual self-reference)
    endow_faculties(agent, agent._rng)   # the full affective endowment (brahmavihāras, ground, prajñā, telos…)
    agent.seed_opinion_text(" ".join(ch.lines))   # lexical opinion -> the camp's banner WORD
    # the SIGNED stance that drives bonding: seeded independent of temperament (so
    # factions on it stay emergent, not homophily on disposition), stable per soul.
    agent.seed_stance(random.Random(hash((agent.id, ch.name)) & 0xFFFFFFFF))
    # an archetype, if given, overlays a distinct SELF on the life-story: its faculty dials,
    # its voice, its value-lean -- so the cast is plural, not six souls of identical wisdom.
    if archetype is not None:
        from agent import archetype as _archetype
        _archetype.apply(agent, archetype)
