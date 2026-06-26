"""Local semantic similarity via an Ollama embedding model (nomic-embed-text).

This is the topic gate for beliefs/ideology: deciding whether a heard line is
ABOUT the same thing an agent believes. Crude word-overlap (Jaccard) can't see
that "the water keeps moving" and "the rain never stops" share a subject;
embeddings can. Vectors are cached per text, so repeated comparisons are free.

Falls back to Jaccard if no embedding model is reachable, so the world still
runs offline-degraded. Tests force the fallback (use_jaccard_only) to stay
deterministic and independent of a running Ollama.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

from agent.memory import _similarity as _jaccard

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
SEMANTIC_TOPIC = 0.55   # cosine: same-subject lines clear this; ~0.45 baseline noise doesn't
JACCARD_TOPIC = 0.15    # fallback word-overlap threshold

_FORCE_JACCARD = False   # tests flip this on for deterministic, Ollama-free runs


class Embedder:
    """Caches one vector per unique text and gives cosine similarity."""

    def __init__(self, model: str = EMBED_MODEL, url: str = OLLAMA_URL) -> None:
        self.model = model
        self.url = url
        self._cache: dict[str, list[float]] = {}
        self._ok: bool | None = None

    def available(self) -> bool:
        if self._ok is None:
            try:
                self.embed("ping")
                self._ok = True
            except (urllib.error.URLError, OSError, KeyError, ValueError):
                self._ok = False
        return self._ok

    def embed(self, text: str) -> list[float]:
        v = self._cache.get(text)
        if v is not None:
            return v
        req = urllib.request.Request(
            f"{self.url}/api/embeddings",
            data=json.dumps({"model": self.model, "prompt": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            v = json.loads(r.read().decode("utf-8"))["embedding"]
        self._cache[text] = v
        return v

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed(a), self.embed(b)
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va)) or 1.0
        nb = math.sqrt(sum(x * x for x in vb)) or 1.0
        return dot / (na * nb)


_E: Embedder | None = None


def _embedder() -> Embedder:
    global _E
    if _E is None:
        _E = Embedder()
    return _E


def use_jaccard_only(flag: bool = True) -> None:
    """Force the word-overlap fallback (used by tests for determinism)."""
    global _FORCE_JACCARD
    _FORCE_JACCARD = flag


def using_embeddings() -> bool:
    """True when real cosine similarity is in use (not the Jaccard fallback).
    Callers normalize their thresholds differently for the two scales."""
    return (not _FORCE_JACCARD) and _embedder().available()


def score(a: str, b: str) -> float:
    """Raw similarity of two lines -- cosine (~0.45 baseline) when embeddings are
    available, else Jaccard overlap. Use for ranking/anchor comparisons."""
    if not a or not b:
        return 0.0
    if not _FORCE_JACCARD:
        e = _embedder()
        if e.available():
            try:
                return e.similarity(a, b)
            except (urllib.error.URLError, OSError, KeyError, ValueError):
                pass
    return _jaccard(a, b)


def topic_match(a: str, b: str) -> bool:
    """True if two lines are about the same thing -- semantic when embeddings
    are available, crude word-overlap otherwise."""
    if not a or not b:
        return False
    if not _FORCE_JACCARD:
        e = _embedder()
        if e.available():
            try:
                return e.similarity(a, b) >= SEMANTIC_TOPIC
            except (urllib.error.URLError, OSError, KeyError, ValueError):
                pass
    return _jaccard(a, b) >= JACCARD_TOPIC
