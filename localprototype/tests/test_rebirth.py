"""Rebirth (samsara): at death the explicit self dissolves into a bardo and only
the vasana ripens into a NEW, identity-less stream -- no author, no self crossing
the gap, population conserved. These pin that the wheel turns correctly and that
the default (rebirth off) behaviour is untouched.

Run:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import Agent, _cosine
from services.llm import MockLLM
from world.sim import World


def _soul(world, sid, life=4, seed=1):
    a = Agent(sid, sid.capitalize(), (10.0, 10.0), "a voice",
              ["the tide and the deep grey stone"], MockLLM(seed=seed), seed=seed, lifespan=life)
    a.seed_opinion_text("the tide and the deep grey stone")
    world.add(a)
    return a


class RebirthTest(unittest.TestCase):
    def _world(self):
        w = World(rebirth_enabled=True)
        w.llm = MockLLM(seed=5)
        return w

    def test_death_dissolves_into_bardo_not_an_heir(self):
        w = self._world()
        seen = []
        w.bus.subscribe("dissolution", lambda sid: seen.append(sid))
        w.bus.subscribe("birth", lambda sid: seen.append(("BIRTH", sid)))  # must NOT fire
        _soul(w, "soul0", life=3)
        for _ in range(5):
            w.step()
        self.assertIn("soul0", seen)                       # it dissolved
        self.assertEqual(len(w._bardo), 1)                 # waiting in the bardo
        self.assertFalse(any(isinstance(s, tuple) for s in seen))  # no authored heir/birth
        self.assertEqual(w.agents, [])                     # gone for now (mid-bardo)

    def test_population_conserved_and_reborn_identityless(self):
        w = self._world()
        born = []
        w.bus.subscribe("rebirth", lambda sid: born.append(sid))
        for i in range(3):
            _soul(w, f"soul{i}", life=4, seed=i)
        for _ in range(70):
            w.step()
        self.assertEqual(len(w.agents), 3)                 # conserved through the wheel
        self.assertEqual(len(born), 3)
        for a in w.agents:
            self.assertTrue(a.id.startswith("stream:"))    # new stream, not a lineage heir
            self.assertNotIn("soul", a.id)                 # no self carried across

    def test_vasana_carries_the_opinion_lean(self):
        # the lean persists across the gap: capture it IN the bardo (at death) and
        # AT rebirth, before the new stream lives and re-grounds its opinion
        w = self._world()
        _soul(w, "soul0", life=3, seed=7)
        captured = {}
        w.bus.subscribe("dissolution", lambda sid: captured.setdefault("death", list(w._bardo[-1]["belief_vec"])))
        w.bus.subscribe("rebirth", lambda sid: captured.setdefault(
            "reborn", list(next(x for x in w.agents if x.id == sid).belief_vec)))
        for _ in range(70):
            w.step()
        self.assertIn("reborn", captured)
        self.assertGreater(_cosine(captured["death"], captured["reborn"]), 0.6)  # perturbed, not random


class NoRebirthUnchangedTest(unittest.TestCase):
    def test_default_world_still_authors_heir_in_grace(self):
        w = World()                                        # rebirth OFF (default)
        w.llm = MockLLM(seed=1)
        births = []
        w.bus.subscribe("birth", lambda sid: births.append(sid))
        a = _soul(w, "river", life=3)
        a.grace = 1.0                                      # dies in grace -> authored heir
        for _ in range(5):
            w.step()
        self.assertEqual(len(w._bardo), 0)                 # no bardo when rebirth is off
        self.assertTrue(births)                            # an heir was authored
        self.assertTrue(any("river." in b for b in births))  # lineage heir, not a stream


if __name__ == "__main__":
    unittest.main()
