"""Swappable LLM backends. Stdlib-only (urllib) to keep the prototype dep-free.

The sim never talks to a model directly -- it builds a SpeechContext and calls
backend.speak(ctx). OllamaLLM renders that to a real local-model call; MockLLM
composes a sentence so the world still runs with no model available. Point the
same interface at the Claude API later without touching agent/sim code.
"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from dataclasses import dataclass, field

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "mannix/llama3.1-8b-abliterated:q5_K_M"


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


class OllamaLLM:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL,
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

    def _system(self, ctx: SpeechContext) -> str:
        return (
            f"You are {ctx.name}. {ctx.persona} "
            f"Right now you feel {_mood_word(ctx.mood)}. "
            "You speak ALOUD to others in a shared world. "
            "Reply with ONE or TWO short spoken sentences only -- no narration, "
            "no stage directions, no quotation marks, no name labels. "
            "Let your wandering thoughts color what you say."
        )

    def _user(self, ctx: SpeechContext) -> str:
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

    def speak(self, ctx: SpeechContext) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system(ctx)},
                {"role": "user", "content": self._user(ctx)},
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


def make_llm(backend: str = "auto", model: str = DEFAULT_MODEL,
             seed: int | None = None):
    """Pick a backend. 'auto' uses Ollama if reachable, else the mock."""
    if backend in ("ollama", "auto"):
        ollama = OllamaLLM(model=model)
        if ollama.available():
            print(f"[llm] using Ollama model: {model}")
            return ollama
        if backend == "ollama":
            raise RuntimeError("Ollama requested but not reachable at " + OLLAMA_URL)
        print("[llm] Ollama not reachable -> falling back to MockLLM")
    else:
        print("[llm] using MockLLM (no model)")
    return MockLLM(seed=seed)
