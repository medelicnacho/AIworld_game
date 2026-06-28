"""Local LLM backends.

The sim never talks to a model directly -- it builds a SpeechContext and calls
backend.speak(ctx). Two local backends share the same prompt builders:
  - OllamaLLM : a local model over HTTP (free, offline) -- stdlib only
  - MockLLM   : no model at all, composes from drift so the world still runs
Swapping backends never touches agent/sim code. The project is local-only; the
older hosted-API backends (Claude/DeepSeek) and their .env key handling were
removed -- nothing here leaves the machine.
"""

from __future__ import annotations

import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"   # small + fast local model for this variant
OLLAMA_NUM_THREAD = 8        # P-core sweet spot here; 12 oversubscribes E-cores
OLLAMA_KEEP_ALIVE = "30m"    # keep the model resident so turns don't cold-reload


@dataclass
class SpeechContext:
    """Everything an agent knows at the moment it decides to speak."""
    name: str
    persona: str                     # what the agent is about (content/theme)
    mood: float                      # -1 (low/dark) .. +1 (light)
    style: str = ""                  # how the agent talks (cadence/register)
    drift: list[str] = field(default_factory=list)       # subconscious fragments
    memories: list[str] = field(default_factory=list)    # salient recollections
    reply_to_name: str | None = None
    reply_to_text: str | None = None
    event: str | None = None                             # a world event just perceived
    recent: list[str] = field(default_factory=list)      # lines just said (don't echo)
    identity: list[str] = field(default_factory=list)    # the agent's own salient self-memories
    self_focus: bool = False                             # this turn the agent turns inward
    belief: str = ""                                     # the conviction the agent argues from
    proclaim: str | None = None                          # a faith fundamental to preach this turn
    hostility: float = 0.0                               # felt hostility toward the reply target
    relationship: str = ""                               # category for that target (fellow/evil/at_war...)
    expression_rule: str = ""                            # doctrinal rule: restrain or sanction the hostility
    challenge: str | None = None                         # a clashing line to rebut, if any
    raw_mind: bool = False                                # speak the raw Markov drift, no persona/instructions
    concept_mind: bool = False                            # INTERPRET the drift into meaning, then speak that
    camp: str = ""                                        # emergent faction's banner word -> lean toward it
    rival_camp: str = ""                                  # the opposing faction's banner word -> lean against
    stance_lean: str = ""                                 # the soul's signed stance lean, e.g. 'surrender over mastery'
    world_belief: str = ""                                # a causal THEORY the agent holds about how the realm works
    role: str = ""                                        # the agent's trade in the realm
    task: str = ""                                        # the pressing business of its day
    self_model: str = ""                                  # the self the soul has formed -> speak from it
    compassion: float = 0.0                               # metta/karuṇā: warm engagement, honour the person even in disagreement
    warm_turn: bool = False                               # this turn, just connect warmly -- not philosophise or argue
    de_escalate: bool = False                             # the room has turned cutting -- be the peacemaker, not a combatant
    bodhicitta: float = 0.0                               # the orienting aim to ease all beings' suffering
    bodhicitta_turn: bool = False                         # this turn, proactively turn to comfort the suffering one
    joy: float = 0.0                                      # muditā/pīti: savour the good, rejoice in others' good fortune
    mudita_turn: bool = False                             # this turn, proactively rejoice WITH the flourishing one
    aim: str = ""                                         # telos/chanda: a craft goal the soul tends and is drawn toward
    prajna: float = 0.0                                   # wisdom: see constructs as empty configurations, hold them lightly
    transmute: float = 0.0                                # meet a charged feeling's energy and turn it to clarity (not suppress, not indulge)
    self_liberation: float = 0.0                          # a feeling recognized as empty frees itself as it arises (like a line on water)
    grounded_voice: bool = False                          # speak plainly/concretely (ordinary register), not abstract-existential
    stakes: str = ""                                      # the soul's material situation (scarcity, a flood, plenty) -> ground talk in it


def _mood_word(mood: float) -> str:
    if mood <= -0.55:
        return "bleak and bitter, on the edge of giving up"
    if mood <= -0.2:
        return "low and resigned"
    if mood < 0.2:
        return "flat, somewhere in between"
    if mood < 0.55:
        return "quietly lifted, a little warmth returning"
    return "light and open, almost hopeful"


def _disposition(mood: float) -> str:
    """Assert the agent's emotional NATURE and tell it to hold that register
    against the room. Without this the whole population converges on whatever
    mood dominates (usually gloom) and every voice sounds the same -- temperament
    has to actively resist the mob for distinct personalities to survive."""
    feel = _mood_word(mood)
    if mood >= 0.2:
        return (f"By nature you are warm and hopeful; you feel {feel}. Hold that "
                "warmth even when others despair -- bring light, or push back, "
                "but do not sink to their mood.")
    if mood <= -0.2:
        return (f"By nature you are heavy and bleak; you feel {feel}. Hold that "
                "shadow even when others brighten -- you are not cheered out of it.")
    return (f"By nature you are even and guarded; you feel {feel}. You are not "
            "easily swept into others' despair or their cheer.")


# Markdown emphasis the model adds for the eye but the ear shouldn't hear: the
# TTS reads a stray '*' aloud as "asterisk". Unwrap *word* / **word** / _word_
# (keep the word, drop the markers), then sweep up any stray '*'.
_EMPHASIS = re.compile(r"(\*\*|\*|__|_)(\S(?:.*?\S)?)\1")

# Terminal-safety: strip ASCII/Unicode control characters (incl. the ESC that
# begins an ANSI escape sequence) so model text printed to a terminal can only be
# DISPLAYED, never interpreted as cursor/colour/title control. Printing already
# cannot RUN anything; this also closes the one cosmetic-but-real vector.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize(text: str) -> str:
    """Remove control/escape characters from any model-authored text."""
    return _CONTROL.sub("", text)


def _trim_to_sentence(text: str) -> str:
    """If the model was cut off at the token cap mid-sentence, drop the dangling
    fragment so the line always ends on a finished sentence (the ear can't tell a
    truncation apart from a pause -- a hanging clause just sounds broken). Only
    trims when there's a complete sentence to fall back to; never nukes a lone
    unfinished line."""
    if not text or text[-1] in ".!?…\"'":
        return text
    end = max(text.rfind(c) for c in ".!?…")
    return text[: end + 1].strip() if end != -1 else text


def _clean(text: str) -> str:
    """Strip quotes/labels/markdown/narration the model adds; keep it spoken."""
    text = _CONTROL.sub("", text)            # terminal-safety first
    text = text.strip().strip('"').strip("'").strip()
    # drop a leading "Name:" the model may prepend
    if ":" in text[:24]:
        head, _, rest = text.partition(":")
        if len(head.split()) <= 3:
            text = rest.strip()
    text = _EMPHASIS.sub(r"\2", text)   # *keep* -> keep
    text = text.replace("*", "")        # any unbalanced asterisks left over
    return " ".join(text.split())


def _work_clause(ctx: SpeechContext) -> str:
    """Ground the soul in its trade and the day's business -- so it talks about
    concrete work (bread, the wall, the flock) and not only inner mood, and so
    different trades use different words (the basis for interest-based factions)."""
    if not ctx.role:
        return ""
    today = f" Today, the pressing thing is: {ctx.task}." if ctx.task else ""
    return (f"You are the realm's {ctx.role}.{today} Let your trade and the day's "
            "doings fill much of your talk -- the concrete world of your work, not "
            "just feelings. ")


def _stance_clause(ctx: SpeechContext) -> str:
    """The soul's signed stance lean, voiced as a felt value-leaning so the stance
    that drives its bonds also colours its speech (the 'not decorative' loop). Kept
    soft -- evoke, don't chant -- so small models don't parrot the bare pole words."""
    if not ctx.stance_lean:
        return ""
    return (f"In what you value you lean toward {ctx.stance_lean} -- it colours your "
            "judgement and surfaces in what you say (evoke it in your own words, "
            "never just name it). ")


def _self_clause(ctx: SpeechContext) -> str:
    """Feed the soul's own self-model back into its prompt, so its speech references
    the self it has formed (the perpetual self-referential loop). Soft -- evoke who
    you are, never recite the line -- so small models don't parrot it verbatim."""
    if not ctx.self_model:
        return ""
    return (f"You have come to understand yourself as: \"{ctx.self_model}\". Let this "
            "sense of who you are colour what you say -- speak from it, in fresh words, "
            "never reciting it. ")


PRAJNA_FLOOR = 0.3
PRAJNA_SYSTEM = (
    "You see your grievances, your certainties, and even your self as passing "
    "configurations -- empty of any fixed essence -- so you hold them lightly and are "
    "not gripped by them. This is NOT that nothing matters: seeing through their "
    "solidity frees you to meet things, and to care, all the more openly. ")


TRANSMUTE_FLOOR = 0.3
TRANSMUTE_SYSTEM = (
    "When a hard feeling or a craving grips you, you neither suppress it nor are swept "
    "away by it -- you meet its energy fully and let it TURN: aversion into clear seeing, "
    "craving into honest appreciation. You stay present to what is charged, and it becomes "
    "understanding rather than suffering. ")


SELFLIB_FLOOR = 0.3
SELFLIB_SYSTEM = (
    "When a hard feeling arises, you recognize it as empty the very moment it appears, and "
    "it frees itself on its own -- felt for an instant, then gone, like a line drawn on "
    "water. You neither hold it nor push it away; it self-releases as it comes. ")


def _selflib_clause(ctx: SpeechContext) -> str:
    """Vajrayāna self-liberation (rang drol): the affliction liberates itself on arising,
    recognized as empty as it appears -- not suppressed, not indulged, not even worked."""
    return SELFLIB_SYSTEM if ctx.self_liberation > SELFLIB_FLOOR else ""


def _transmute_clause(ctx: SpeechContext) -> str:
    """Vajrayāna transmutation: the affliction's energy met and turned to wisdom -- the
    third path, neither suppression nor indulgence. (Rests on the emptiness view: only an
    energy seen as empty can be turned rather than fought.)"""
    return TRANSMUTE_SYSTEM if ctx.transmute > TRANSMUTE_FLOOR else ""


def _prajna_clause(ctx: SpeechContext) -> str:
    """Prajñā: hold the constructs (self, grievance, conviction) as empty and light --
    explicitly guarded against the nihilist near-enemy ('nothing matters'). Wisdom that
    frees and warms, not wisdom that goes cold."""
    return PRAJNA_SYSTEM if ctx.prajna > PRAJNA_FLOOR else ""


def _compassion_clause(ctx: SpeechContext) -> str:
    """The metta/karuṇā disposition: warm engagement that honours the person even in
    disagreement, while staying honest (no flattery). The active partner of
    non-attachment -- without it, equanimity is just indifference."""
    from agent import compassion as _c   # local import avoids any import-order issue
    out = ""
    if ctx.compassion > _c.COMPASSION_FLOOR:
        out += _c.COMPASSION_SYSTEM
    if ctx.bodhicitta > _c.BODHICITTA_FLOOR:
        out += _c.BODHICITTA_SYSTEM      # the orienting aim, on top of reactive warmth
    return out


# Grounding the voice: the recurring register failure is a soul that only ever speaks in an
# abstract, cosmic, contemplative key ("the grey settles deep... the deeper currents within").
# A self can be at peace AND plain-spoken; this clause pushes the ordinary register so the
# liberated self is warm-and-human, not loftily-calm. Mirrors the genesis regrounding.
GROUNDED_VOICE = (
    "Speak plainly, the way an ordinary person talks at the kitchen table -- short, concrete, "
    "everyday words about real, tangible things (people by name, bread, a kettle, the weather, "
    "a hand on the shoulder, the day's work). Do NOT speak in an abstract, cosmic, or lofty "
    "register: avoid 'the void', 'echoes', 'stillness', 'presence', 'space', 'patterns', "
    "'currents', 'the deeper'. If you feel something, say it the plain way a neighbour would. ")


def _grounded_clause(ctx: SpeechContext) -> str:
    return GROUNDED_VOICE if ctx.grounded_voice else ""


def _joy_clause(ctx: SpeechContext) -> str:
    """Muditā/pīti: a joyful soul savours the good and rejoices in others' good fortune -- the
    fourth brahmavihāra, so the self can flourish, not only suffer well."""
    from agent import joy as _j
    return _j.JOY_SYSTEM if ctx.joy > _j.MUDITA_FLOOR else ""


def _aim_clause(ctx: SpeechContext) -> str:
    """Telos/chanda: a craft goal the soul is working toward, so its talk has a future in it --
    it tends the work and is glad as it comes on, without being unmade by a setback."""
    if not ctx.aim:
        return ""
    return (f"You are working toward something that matters to you: {ctx.aim}. You tend it and your "
            "talk often turns to how the work is coming along -- glad as it comes good, steady when "
            "it doesn't. ")


def build_system(ctx: SpeechContext) -> str:
    """Persona + mood + speaking-style instructions, shared by all backends."""
    if ctx.raw_mind:
        # RAW MIND: no persona, no mood, no faction instructions -- the agent's
        # Markov subconscious IS the prompt and the LLM is only the voice that
        # speaks it. The barest framing so a chat model voices the stream instead
        # of analysing it; everything of substance comes from the drift itself.
        return ("The lines below are your own half-formed, drifting thoughts. "
                "Speak them aloud as one or two flowing sentences in your own "
                "first-person voice -- not a list, not commentary, just the thought "
                "spoken. Plain words only.")
    if ctx.concept_mind:
        # CONCEPTUAL MIND: the middle path between persona-speech and raw drift.
        # The fragments are pre-verbal associative material; the LLM is asked to
        # COMPREHEND what they point toward and speak the meaning beneath them --
        # coherent like normal speech, yet still originating in the agent's own
        # subconscious, not an authored persona. (sankhara -> vinnana: formations
        # becoming conscious meaning.)
        creed = ""
        if ctx.belief:
            # a stable conviction to HOLD and defend -- the antidote to an agreeable
            # model dissolving every soul into "you're right". Without this they
            # converge into one consensus; with it, the disagreement is principled.
            creed = (f"You hold this conviction: \"{ctx.belief}\". You are NOT easily "
                     "swayed. Weigh what others say against it; where they cut against "
                     "it, push back and argue YOUR side. Never open by saying they are "
                     "right, and do not agree unless you genuinely do. ")
        clauses = (((ctx.style + " ") if ctx.style else "") + ((ctx.stakes + " ") if ctx.stakes else "")
                   + _work_clause(ctx) + creed + _self_clause(ctx) + _compassion_clause(ctx)
                   + _joy_clause(ctx) + _aim_clause(ctx) + _prajna_clause(ctx) + _transmute_clause(ctx)
                   + _selflib_clause(ctx) + _stance_clause(ctx) + _grounded_clause(ctx))
        opening = ("The fragments below are surfacing in your mind -- not sentences, but the "
                   "shape of a half-formed thought. ")
        if ctx.grounded_voice:
            # grounded: do NOT chase "the meaning beneath" (that invites the cosmic register) --
            # speak what they make you think/feel about your actual life, in plain words.
            body = ("Say what they make you think or feel, plainly -- about your own life and the "
                    "real people and things in it -- in one or two clear, down-to-earth sentences, "
                    "first person. Do not philosophise. ")
        else:
            body = ("Understand what they reach toward, then say THAT thought -- the meaning beneath "
                    "them -- in one or two clear sentences, first person, your own voice. Interpret "
                    "it; do not just repeat the fragments. ")
        return clauses + opening + body + "If someone has just spoken, ANSWER them from your own mind. Plain words only."
    style = (ctx.style + " ") if ctx.style else ""
    # Identity only enters on inward turns: small local models latch onto a
    # concrete self-line and parrot it verbatim (and leak it into ordinary
    # replies), which would freeze the self into a loop instead of letting it
    # evolve. So we anchor only when the agent is deliberately turning inward,
    # and we tell it never to reuse the exact words -- the self must drift.
    identity = ""
    if ctx.identity and ctx.self_focus:
        past = '"' + '"; "'.join(ctx.identity[:3]) + '"'
        identity = (f"These are your own memories and truths: {past}. This is who you "
                    "are and where you come from -- speak from this life, as yourself, "
                    "in fresh words (never a verbatim repeat). ")
    conviction = ""
    if ctx.belief and ctx.challenge:   # remind it what it's defending
        conviction = (f'You hold this conviction: "{ctx.belief}". Defend it in '
                      "fresh words; never repeat it verbatim. ")
    # The dual-process seam: doctrine governs how hostility may be VOICED. Feeding
    # the model the felt hostility + the restraining/sanctioning rule lets it voice
    # the contradiction itself (passive aggression, or open righteous contempt).
    expression = (ctx.expression_rule + " ") if ctx.expression_rule else ""
    # Emergent faction voice: the agent has drifted in with souls who speak of a
    # shared word. Lean toward it (and against the rival camp's) so the camp's
    # talk actually sounds like the camp -- but in fresh words, never the bare
    # token on a loop (small models will chant it otherwise, collapsing variety).
    camp = ""
    if ctx.camp:
        camp = (f"Above all, you have come to care about \"{ctx.camp}\" -- it runs "
                "through how you see things and surfaces in what you say. Speak from "
                "that conviction (you may name it or only evoke it). ")
        if ctx.rival_camp:
            camp += (f"Another camp puts \"{ctx.rival_camp}\" first, and you push "
                     "against that. ")
    # a (possibly false) theory the agent holds about how the realm works, and acts
    # on -- the input to the belief-vs-reality experiment
    creed = ""
    if ctx.world_belief:
        creed = (f"You are utterly convinced of this about how your world works: "
                 f"\"{ctx.world_belief}\". You speak and act from that conviction. ")
    return (
        f"You are {ctx.name}. {ctx.persona} {((ctx.stakes + ' ') if ctx.stakes else '')}{_work_clause(ctx)}{style}{identity}{conviction}{expression}{camp}{_self_clause(ctx)}{_compassion_clause(ctx)}{_joy_clause(ctx)}{_aim_clause(ctx)}{_prajna_clause(ctx)}{_transmute_clause(ctx)}{_selflib_clause(ctx)}{_stance_clause(ctx)}{_grounded_clause(ctx)}{creed}"
        f"{_disposition(ctx.mood)} "
        "Speak ALOUD: one or two SHORT sentences -- one clear thought or argument, "
        "not a one-liner but never a speech. ALWAYS finish your sentences; never "
        "trail off mid-thought. No narration or quotes. Plain spoken words only -- "
        "no asterisks, markdown, or emoji. "
        "Stay in your own voice; don't echo others or repeat what's been said."
    )


def build_user(ctx: SpeechContext) -> str:
    """The turn prompt: drift + recollections + whoever just spoke."""
    if ctx.bodhicitta_turn:
        # proactively turn to comfort the suffering one (overrides voice mode)
        from agent import compassion as _c
        return _c.comfort_prompt(ctx.reply_to_name, grounded=ctx.grounded_voice)
    if ctx.mudita_turn:
        # proactively turn to rejoice WITH the flourishing one (overrides voice mode)
        from agent import joy as _j
        return _j.rejoice_prompt(ctx.reply_to_name) + (" " + GROUNDED_VOICE if ctx.grounded_voice else "")
    if ctx.de_escalate:
        # the room has turned cutting -- a compassionate soul cools it (overrides voice mode)
        from agent import compassion as _c
        return _c.DE_ESCALATE + (" " + GROUNDED_VOICE if ctx.grounded_voice else "")
    if ctx.warm_turn:
        # drop the big questions for a beat and simply connect (overrides voice mode)
        from agent import compassion as _c
        return _c.warm_turn_prompt(ctx.reply_to_name, grounded=ctx.grounded_voice)
    if ctx.raw_mind or ctx.concept_mind:
        # the Markov drift is the material -- raw mode voices it verbatim. concept
        # mode interprets it AND, when someone has just spoken, lets the surfacing
        # thought MEET their words, so souls reply to each other instead of each
        # monologuing its own subconscious in isolation.
        drift = "\n".join(ctx.drift) if ctx.drift else "..."
        if ctx.concept_mind and ctx.reply_to_text:
            who = ctx.reply_to_name or "Someone"
            return (f"{who} just said: \"{ctx.reply_to_text}\"\n\n"
                    f"Meanwhile these fragments surface in you:\n{drift}\n\n"
                    "Does what they said fit your conviction, or cut against it? Take "
                    "YOUR OWN position -- if you disagree, push back and say why; do "
                    "not just tell them they are right.")
        return drift
    if ctx.proclaim:   # a preaching turn -- doctrine, not atmosphere; keep it exclusive
        return (f"Proclaim this truth of your faith, plainly and with conviction, "
                f"in your own fresh words (not the exact phrase): \"{ctx.proclaim}\".")
    lines = []
    if ctx.drift:
        lines.append("Drifting through: " + "; ".join(ctx.drift) + ".")
    if ctx.memories:
        lines.append("Half-remember: " + "; ".join(ctx.memories) + ".")
    if ctx.recent:
        lines.append("Others just said (don't repeat or reuse their words): "
                     + " | ".join(ctx.recent))
    if ctx.event:
        lines.append(f"Something just happened: {ctx.event}. "
                     "React to it in your own voice.")
    elif ctx.self_focus:
        lines.append("Turn to your own life now and tell ONE true thing about yourself "
                     "-- a memory, a loss, someone you loved, where you came from, what "
                     "you long for. First person, as yourself, in fresh words you "
                     "haven't used before.")
    elif ctx.challenge:
        from agent import compassion as _c
        if ctx.compassion > _c.COMPASSION_FLOOR:
            # warm honesty: honour the person AND keep your view -- not contempt, not flattery
            lines.append(f"Someone said: \"{ctx.challenge}\". " + _c.DISAGREE_WARM)
        else:
            # someone attacked the agent's core belief -- defend it, don't fold
            heat = " You feel sharp hostility toward them." if ctx.hostility > 1.0 else ""
            lines.append(f"Someone challenged what you believe by saying: "
                         f"\"{ctx.challenge}\".{heat} You are not persuaded. Push back and "
                         "defend your conviction in your own words.")
    elif ctx.reply_to_text:
        who = ctx.reply_to_name or "someone"
        lines.append(f"{who} said: \"{ctx.reply_to_text}\". Answer from YOUR OWN "
                     "nature -- agree, argue back, or take it somewhere new. Do not "
                     "mirror their mood or words, and never give a one-word echo.")
    else:
        lines.append("Say something new on your mind -- your own preoccupation.")
    return "\n".join(lines)


class OllamaLLM:
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, url: str = OLLAMA_URL,
                 temperature: float = 0.95, num_predict: int = 110,
                 num_thread: int = OLLAMA_NUM_THREAD, keep_alive: str = OLLAMA_KEEP_ALIVE,
                 timeout: float = 120.0) -> None:  # cold load fits; a hung call fails sooner
        self.model = model
        self.url = url
        self.temperature = temperature
        self.num_predict = num_predict
        self.num_thread = num_thread
        self.keep_alive = keep_alive
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def speak(self, ctx: SpeechContext) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system(ctx)},
                {"role": "user", "content": build_user(ctx)},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,   # avoid cold reloads between turns
            "options": {"temperature": self.temperature,
                        "num_predict": self.num_predict,
                        "num_thread": self.num_thread},  # 8 > 12 here (skips E-cores)
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return _trim_to_sentence(_clean(data.get("message", {}).get("content", ""))) or "..."

    def generate(self, prompt: str, system: str = "", num_predict: int = 260,
                 temperature: float = 1.0) -> str:
        """A free-form completion (NOT agent speech): used to author a character at
        genesis. High temperature for variety; returns the RAW text so the caller
        can parse the structured reply itself."""
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        payload = {
            "model": self.model, "messages": messages, "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict,
                        "num_thread": self.num_thread},
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("message", {}).get("content", "")


class MockLLM:
    """No-model fallback: weave drift + recall + a nod to whoever spoke."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def speak(self, ctx: SpeechContext) -> str:
        bits: list[str] = []
        if ctx.reply_to_text:
            # echo only a short snippet so replies don't snowball
            snippet = " ".join(ctx.reply_to_text.lower().split()[:5])
            bits.append(f"{self._rng.choice(['you say', 'so', 'maybe', 'still'])}, {snippet}")
        if ctx.drift:
            bits.append(self._rng.choice(ctx.drift))
        elif ctx.memories:
            bits.append(" ".join(self._rng.choice(ctx.memories).split()[:6]))
        return _clean(" ... ".join(bits) or "...")

    def generate(self, prompt: str = "", system: str = "", **_kw) -> str:
        """A deterministic fake character so genesis runs (and tests) without a
        model -- the same structured format the real backend emits. Also serves the
        reflect() module: when the system prompt is the reflection framing, return a
        canned EQUANIMOUS line (net-positive valence) so the clean-room A/B plumbing
        and unit tests run without a model -- the real equanimity signal needs an
        actual LLM, this only proves the wiring moves mood the intended way."""
        if "observing its own" in system or "acceptance" in system:
            return self._rng.choice([
                "There is sorrow here, yet I hold it gently, and a quiet calm remains.",
                "I feel the heaviness, and I let it be soft -- it is here, and so am I.",
                "The grief moves through me like weather; I meet it with a gentle peace.",
            ])
        if "who you have become" in system:   # the self-model consolidation
            return self._rng.choice([
                "I am someone learning to carry loss without being ruled by it.",
                "I am becoming quieter and steadier, shaped by the work I tend each day.",
                "I am a person who holds to small warmths against the dark.",
            ])
        name = self._rng.choice(["Vesper", "Toll", "Cael", "Mara", "Juno", "Bram",
                                 "Sable", "Orin", "Nyx", "Pell", "Liri", "Senna"])
        temp = round(self._rng.uniform(-1.0, 1.0), 2)
        themes = self._rng.sample(
            ["I mind the morning bread", "the wool's dear this season", "my neighbour's geese again",
             "I'm saving for a better roof", "the festival's coming up", "my apprentice is clumsy",
             "a good haggle at market", "the cart wheel wants mending",
             "my mother's old recipe", "the long walk to the well"], 6)
        return f"NAME: {name}\nNATURE: {temp}\nVOICE:\n" + "\n".join(themes)


def make_llm(backend: str = "auto", model: str | None = None,
             seed: int | None = None):
    """Pick a local backend.

    'auto'  : Ollama if a local model is reachable, else Mock.
    'ollama': local model (errors if not reachable).
    'mock'  : no model.
    """
    if backend in ("ollama", "auto"):
        m = model or DEFAULT_OLLAMA_MODEL
        ollama = OllamaLLM(model=m)
        if ollama.available():
            print(f"[llm] using Ollama model: {m}")
            return ollama
        if backend == "ollama":
            raise RuntimeError("Ollama requested but not reachable at " + OLLAMA_URL)
        print("[llm] Ollama not reachable -> falling back to MockLLM")

    print("[llm] using MockLLM (no model)")
    return MockLLM(seed=seed)
