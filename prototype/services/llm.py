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
DEFAULT_OLLAMA_MODEL = "mannix/llama3.1-8b-abliterated:q5_K_M"
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"


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
    persona: str
    mood: float                      # -1 (low/dark) .. +1 (light)
    drift: list[str] = field(default_factory=list)       # subconscious fragments
    memories: list[str] = field(default_factory=list)    # salient recollections
    reply_to_name: str | None = None
    reply_to_text: str | None = None


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
    return (
        f"You are {ctx.name}. {ctx.persona} "
        f"Right now you feel {_mood_word(ctx.mood)}. "
        "You speak ALOUD to others in a shared world. "
        "Reply with ONE short spoken sentence -- under 15 words, no narration, "
        "no stage directions, no quotation marks, no name labels. "
        "Let your wandering thoughts color what you say."
    )


def build_user(ctx: SpeechContext) -> str:
    """The turn prompt: drift + recollections + whoever just spoke."""
    lines = []
    if ctx.drift:
        lines.append("Your mind is drifting through: " + "; ".join(ctx.drift) + ".")
    if ctx.memories:
        lines.append("You half-remember: " + "; ".join(ctx.memories) + ".")
    if ctx.reply_to_text:
        who = ctx.reply_to_name or "someone"
        lines.append(f"{who} just said to you: \"{ctx.reply_to_text}\". "
                     "Respond to them, in your own voice.")
    else:
        lines.append("Say what is surfacing in you right now.")
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

    'auto'  : Claude if a key is present, else Ollama if reachable, else Mock.
    'claude': Claude API (errors if no key / package).
    'ollama': local model (errors if not reachable).
    'mock'  : no model.
    """
    load_dotenv()

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
