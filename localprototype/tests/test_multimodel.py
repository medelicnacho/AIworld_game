"""Tests for per-agent models: different NPCs can run different backends at once.

The world hands each Agent its own LLM, so a cast can mix models (River on one,
Ash on another). These assert build_world wires a distinct backend to each agent
and that each agent actually speaks through its own model.

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_multimodel.py
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

# allow `python tests/test_multimodel.py` from anywhere

import main
from services.tts import NullTTS


class TagLLM:
    """A backend that stamps its tag on every line, so we can tell who spoke it."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def speak(self, ctx) -> str:
        return f"line from {self.tag}"


def _silent():
    """Swallow build/run stdout+stderr so test output stays clean."""
    return redirect_stdout(io.StringIO())


class MultiModelTest(unittest.TestCase):
    def test_each_agent_gets_its_own_backend(self):
        llms = [TagLLM(f"m{i}") for i in range(len(main.PERSONAS))]
        with _silent():
            world = main.build_world(llms, NullTTS(), seed=7, show_think=False,
                                     show_text=False, events_enabled=False)
        self.assertEqual([a.llm.tag for a in world.agents],
                         [f"m{i}" for i in range(len(main.PERSONAS))])

    def test_a_single_backend_is_shared_by_all(self):
        one = TagLLM("solo")
        with _silent():
            world = main.build_world(one, NullTTS(), seed=7, show_think=False,
                                     show_text=False, events_enabled=False)
        self.assertTrue(all(a.llm is one for a in world.agents),
                        "passing one backend must share it across the cast")

    def test_agents_speak_through_their_own_model(self):
        llms = [TagLLM(f"m{i}") for i in range(len(main.PERSONAS))]
        spoken: list[str] = []
        with _silent():
            world = main.build_world(llms, NullTTS(), seed=7, show_think=False,
                                     show_text=False, events_enabled=False)
        world.bus.subscribe("utterance", lambda u: spoken.append(u.text))
        with _silent(), redirect_stderr(io.StringIO()):
            world.run(40)
        # over a run, lines from more than one distinct model should appear
        tags = {t.replace("line from ", "") for t in spoken}
        self.assertGreater(len(tags), 1,
                           "multiple different models should have spoken")
        self.assertTrue(tags.issubset({f"m{i}" for i in range(len(main.PERSONAS))}))


if __name__ == "__main__":
    unittest.main()


class OllamaAvailableChecksTheModelTest(unittest.TestCase):
    """available() must mean "this MODEL can speak", not "a server answered".
    Found live: ollama installed for embeddings only -- /api/tags answered 200,
    the cockpit enabled the gemma3:4b talk voice, and every talk hung on a model
    that was never pulled. Pin: a served tag list WITHOUT the model is False,
    WITH it is True (including the bare-name == :latest ollama convention)."""

    def _fake_tags(self, names):
        import io as _io
        import json as _json

        class _Resp(_io.BytesIO):
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False

        return _Resp(_json.dumps({"models": [{"name": n} for n in names]}).encode())

    def test_server_up_but_model_missing_is_not_available(self):
        import urllib.request
        from services.llm import OllamaLLM
        real = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: self._fake_tags(["nomic-embed-text:latest"])
        try:
            self.assertFalse(OllamaLLM(model="gemma3:4b").available())
        finally:
            urllib.request.urlopen = real

    def test_present_model_is_available_and_bare_name_means_latest(self):
        import urllib.request
        from services.llm import OllamaLLM
        real = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: self._fake_tags(
            ["gemma3:4b", "nomic-embed-text:latest"])
        try:
            self.assertTrue(OllamaLLM(model="gemma3:4b").available())
            urllib.request.urlopen = lambda *a, **k: self._fake_tags(
                ["gemma3:4b", "nomic-embed-text:latest"])
            self.assertTrue(OllamaLLM(model="nomic-embed-text").available())
        finally:
            urllib.request.urlopen = real
