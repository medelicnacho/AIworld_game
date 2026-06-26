"""Swappable LLM backends.

The sim never talks to a model directly -- it builds a SpeechContext and calls
backend.speak(ctx). Three backends share the same prompt builders:
  - ClaudeLLM : Claude API (fast, real-time) -- needs the `anthropic` package + key
  - OllamaLLM : local model over HTTP (free, offline) -- stdlib only
  - MockLLM   : no model at all, composes from drift so the world still runs
Swapping backends never touches agent/sim code.
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"   # small + fast local model for this variant
OLLAMA_NUM_THREAD = 8        # P-core sweet spot here; 12 oversubscribes E-cores
OLLAMA_KEEP_ALIVE = "30m"    # keep the model resident so turns don't cold-reload
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


def load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader: KEY=VALUE lines into os.environ (no overwrite).

    Keeps secrets (ANTHROPIC_API_KEY) out of source and out of shell history.
    """
    env_path = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


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
        return ("The fragments below are surfacing in your mind -- not sentences, "
                "but the shape of a half-formed thought. Understand what they are "
                "reaching toward, then say THAT thought -- the meaning beneath them "
                "-- in one or two clear sentences, first person, your own voice. "
                "Interpret it; do not just repeat the fragments. Plain words only.")
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
    return (
        f"You are {ctx.name}. {ctx.persona} {style}{identity}{conviction}{expression}{camp}"
        f"{_disposition(ctx.mood)} "
        "Speak ALOUD: one or two SHORT sentences -- one clear thought or argument, "
        "not a one-liner but never a speech. ALWAYS finish your sentences; never "
        "trail off mid-thought. No narration or quotes. Plain spoken words only -- "
        "no asterisks, markdown, or emoji. "
        "Stay in your own voice; don't echo others or repeat what's been said."
    )


def build_user(ctx: SpeechContext) -> str:
    """The turn prompt: drift + recollections + whoever just spoke."""
    if ctx.raw_mind or ctx.concept_mind:
        # the Markov drift IS the material -- raw mode voices it, concept mode
        # interprets it; either way nothing else is fed in
        return "\n".join(ctx.drift) if ctx.drift else "..."
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


class ClaudeLLM:
    """Claude API backend (uses the official anthropic SDK). Fast, real-time."""

    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL, max_tokens: int = 110,
                 timeout: float = 30.0) -> None:
        import anthropic  # lazy -- only this backend needs the package
        self.model = model
        self.max_tokens = max_tokens
        # reads ANTHROPIC_API_KEY from the environment (loaded from .env)
        self._client = anthropic.Anthropic(timeout=timeout)

    @staticmethod
    def available() -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def speak(self, ctx: SpeechContext) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=build_system(ctx),
            messages=[{"role": "user", "content": build_user(ctx)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        return _clean(text) or "..."


class DeepSeekLLM:
    """DeepSeek API backend (OpenAI-compatible). Cheapest scalable option.

    Stdlib HTTP -- no SDK needed. China-hosted, so benchmark latency before
    relying on it for real-time play.
    """

    def __init__(self, model: str = DEFAULT_DEEPSEEK_MODEL, url: str = DEEPSEEK_URL,
                 temperature: float = 0.95, max_tokens: int = 110,
                 timeout: float = 30.0) -> None:
        self.model = model
        self.url = url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._key = os.environ.get("DEEPSEEK_API_KEY", "")

    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    def speak(self, ctx: SpeechContext) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system(ctx)},
                {"role": "user", "content": build_user(ctx)},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
            # v4-flash defaults to thinking mode, which burns the token budget on
            # reasoning and returns empty content. Disable it for fast one-liners.
            "thinking": {"type": "disabled"},
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return _clean(text) or "..."


class OllamaLLM:
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, url: str = OLLAMA_URL,
                 temperature: float = 0.95, num_predict: int = 110,
                 num_thread: int = OLLAMA_NUM_THREAD, keep_alive: str = OLLAMA_KEEP_ALIVE,
                 timeout: float = 180.0) -> None:  # generous for cold model load
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
        model -- the same structured format the real backend emits."""
        name = self._rng.choice(["Vesper", "Toll", "Cael", "Mara", "Juno", "Bram",
                                 "Sable", "Orin", "Nyx", "Pell", "Liri", "Senna"])
        temp = round(self._rng.uniform(-1.0, 1.0), 2)
        themes = self._rng.sample(
            ["the tide remembers", "old stone keeps its silence", "grey light at the edge",
             "a slow hunger underneath", "dying embers and ash", "deep roots in the dark",
             "the humming of the machine", "salt and rust on the wind",
             "falling snow erases all", "a locked door nobody opens"], 6)
        return f"NAME: {name}\nNATURE: {temp}\nVOICE:\n" + "\n".join(themes)


def make_llm(backend: str = "auto", model: str | None = None,
             seed: int | None = None):
    """Pick a backend.

    'auto'    : DeepSeek if key present (cheap+fast), else Claude, else Ollama, else Mock.
    'deepseek': DeepSeek API (errors if no key).
    'claude'  : Claude API (errors if no key / package).
    'ollama'  : local model (errors if not reachable).
    'mock'    : no model.
    """
    load_dotenv()

    if backend in ("deepseek", "auto") and DeepSeekLLM.available():
        m = model or DEFAULT_DEEPSEEK_MODEL
        print(f"[llm] using DeepSeek API model: {m}")
        return DeepSeekLLM(model=m)
    if backend == "deepseek":
        raise RuntimeError(
            "DeepSeek requested but no DEEPSEEK_API_KEY (set it in prototype/.env)."
        )

    if backend in ("claude", "auto") and ClaudeLLM.available():
        m = model or DEFAULT_CLAUDE_MODEL
        print(f"[llm] using Claude API model: {m}")
        return ClaudeLLM(model=m)
    if backend == "claude":
        raise RuntimeError(
            "Claude requested but unavailable. Set ANTHROPIC_API_KEY (e.g. in "
            "prototype/.env) and `pip install anthropic` in the project venv."
        )

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
