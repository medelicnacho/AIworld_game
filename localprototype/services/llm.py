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
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"   # small + fast local model for this variant
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
    recent: list[str] = field(default_factory=list)      # lines just said (don't echo)


def _mood_word(mood: float) -> str:
    if mood <= -0.3:
        return "heavy and withdrawn"
    if mood >= 0.3:
        return "light and open"
    return "flat, somewhere in between"


def _clean(text: str) -> str:
    """Strip quotes/labels/narration the model sometimes adds; keep it spoken."""
    text = text.strip().strip('"').strip("'").strip()
    # drop a leading "Name:" the model may prepend
    if ":" in text[:24]:
        head, _, rest = text.partition(":")
        if len(head.split()) <= 3:
            text = rest.strip()
    return " ".join(text.split())


def build_system(ctx: SpeechContext) -> str:
    """Persona + mood + speaking-style instructions, shared by all backends."""
    style = (ctx.style + " ") if ctx.style else ""
    return (
        f"You are {ctx.name}. {ctx.persona} "
        f"{style}"
        f"Right now you feel {_mood_word(ctx.mood)}. "
        "You speak ALOUD to others in a shared world. "
        "Reply with ONE short spoken sentence -- under 15 words, no narration, "
        "no stage directions, no quotation marks, no name labels. "
        "Stay true to your own VOICE -- don't mirror how others talk. "
        "Not every line is a profound metaphor: sometimes it's plain, blunt, "
        "mundane, a question, or a complaint. "
        "Avoid repeating words or ideas already said; let the talk wander."
    )


def build_user(ctx: SpeechContext) -> str:
    """The turn prompt: drift + recollections + whoever just spoke."""
    lines = []
    if ctx.drift:
        lines.append("Your mind is drifting through: " + "; ".join(ctx.drift) + ".")
    if ctx.memories:
        lines.append("You half-remember: " + "; ".join(ctx.memories) + ".")
    if ctx.recent:
        lines.append("Just said by others (do NOT restate these ideas or reuse their "
                     "words -- add a new thought or change the subject): "
                     + " | ".join(ctx.recent))
    if ctx.reply_to_text:
        who = ctx.reply_to_name or "someone"
        lines.append(f"{who} just said to you: \"{ctx.reply_to_text}\". "
                     "React, but take it somewhere new -- don't echo it.")
    else:
        lines.append("Bring up something new surfacing in you right now -- "
                     "your own preoccupation, not the current topic.")
    return "\n".join(lines)


class ClaudeLLM:
    """Claude API backend (uses the official anthropic SDK). Fast, real-time."""

    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL, max_tokens: int = 48,
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
                 temperature: float = 0.95, max_tokens: int = 48,
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
                 temperature: float = 0.95, num_predict: int = 60,
                 timeout: float = 180.0) -> None:  # generous for cold model load
        self.model = model
        self.url = url
        self.temperature = temperature
        self.num_predict = num_predict
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
            "options": {"temperature": self.temperature,
                        "num_predict": self.num_predict},
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return _clean(data.get("message", {}).get("content", "")) or "..."


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
