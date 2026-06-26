"""Procedural genesis: the LLM authors a soul (name + disposition + inner voice)
that seeds the Markov subconscious. These pin the parsing (which must survive a
malformed reply) and the seeding (the generated voice must actually become the
agent's memory + opinion).

Run:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import genesis
from agent.agent import Agent
from services.llm import MockLLM


class ParseTest(unittest.TestCase):
    def test_parses_well_formed_reply(self):
        raw = "NAME: Vesper\nNATURE: -0.6\nVOICE:\nthe tide remembers\ncold iron and rust"
        ch = genesis.parse_character(raw, random.Random(1))
        self.assertEqual(ch.name, "Vesper")
        self.assertAlmostEqual(ch.temperament, -0.6)
        self.assertEqual(ch.lines, ["the tide remembers", "cold iron and rust"])

    def test_strips_numbering_and_bullets(self):
        raw = "NAME: Toll\nNATURE: 0.2\nVOICE:\n1. the old door\n- a slow hunger"
        ch = genesis.parse_character(raw, random.Random(1))
        self.assertEqual(ch.lines, ["the old door", "a slow hunger"])

    def test_malformed_reply_falls_back(self):
        ch = genesis.parse_character("garbage with no fields", random.Random(2))
        self.assertTrue(ch.name)                      # a random fallback name
        self.assertTrue(-1.0 <= ch.temperament <= 1.0)
        self.assertGreaterEqual(len(ch.lines), 1)     # fallback themes

    def test_temperament_clamped(self):
        ch = genesis.parse_character("NAME: X\nNATURE: 5.0\nVOICE:\na line here", random.Random(1))
        self.assertEqual(ch.temperament, 1.0)


class GenerateTest(unittest.TestCase):
    def test_mock_generates_distinct_souls(self):
        llm = MockLLM(seed=7)
        a = genesis.generate_character(llm)
        b = genesis.generate_character(llm)
        self.assertTrue(a.name and b.name)
        self.assertNotEqual((a.name, a.lines), (b.name, b.lines))   # distinct selves


class SeedTest(unittest.TestCase):
    def _agent(self):
        return Agent("river", "Placeholder", (0.0, 0.0), "", [], MockLLM(seed=1), seed=1)

    def test_seed_pours_soul_into_agent(self):
        a = self._agent()
        ch = genesis.Character("Vesper", -0.5, ["the tide remembers", "cold iron"])
        genesis.seed_agent(a, ch)
        self.assertEqual(a.name, "Vesper")
        self.assertEqual(a.temperament, -0.5)
        self.assertEqual(a.phrases, ["the tide remembers", "cold iron"])
        self.assertTrue(a.belief_grounded)                       # opinion seeded
        self.assertTrue(any("tide" in m.text for m in a.memory.items))  # in the Markov corpus

    def test_fresh_wipes_inherited_memory(self):
        a = self._agent()
        a.memory.write("an inherited memory", tick=0, source="self")
        genesis.seed_agent(a, genesis.Character("Nyx", 0.3, ["new self lines"]), fresh=True)
        self.assertFalse(any("inherited" in m.text for m in a.memory.items))
        self.assertTrue(any("new self" in m.text for m in a.memory.items))


if __name__ == "__main__":
    unittest.main()
