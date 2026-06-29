"""Tests for reflect() wired into the live World (World.reflect_turn).

Deterministic plumbing checks (MockLLM's canned reflection line; Jaccard, so no nomic needed -- the
reflection MEMORY is written regardless of the equanimity read). The grooving itself (reflection ->
cultivate -> grip down) is the equanimity mechanism validated in experiment_path / experiment_world_practice.
"""

import unittest

from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World


def _soul(sid, reflect_on):
    a = Agent(sid, sid, (0.0, 0.0), "You are a working soul.", ["I work my trade"],
              MockLLM(seed=1), seed=1, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = 0.70, 0.10, True
    a.reflect_enabled = reflect_on
    a.memory.write("a hard season, and a loss I carry", tick=0, source="self",
                   speaker_id=sid, emotion=-0.5)
    return a


def _world():
    w = World(move_seed=1)
    w.llm = MockLLM(seed=1)
    return w


class ReflectTurnTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_reflect_turn_writes_a_reflection_for_an_eligible_soul(self):
        w = _world()
        a = _soul("s0", reflect_on=True)
        w.add(a)
        before = sum(1 for m in a.memory.items if m.source == "reflection")
        text = w.reflect_turn()
        after = sum(1 for m in a.memory.items if m.source == "reflection")
        self.assertIsNotNone(text)
        self.assertEqual(after, before + 1)   # the soul met its own mind -> a reflection was imprinted

    def test_reflect_turn_skips_ineligible_souls(self):
        w = _world()
        a = _soul("s0", reflect_on=False)     # reflect_enabled is off
        w.add(a)
        self.assertIsNone(w.reflect_turn())
        self.assertFalse(any(m.source == "reflection" for m in a.memory.items))

    def test_reflect_turn_is_a_noop_with_no_souls(self):
        self.assertIsNone(_world().reflect_turn())


if __name__ == "__main__":
    unittest.main()
