"""Tests for the Grace of the Creator (the theology / selection layer).

Agents are born in grace. Grace makes their data effective (slow forgetting,
hard-imprinting words) and gates reproduction at death. It falls with entropy
and heresy, renews with communion and faithful speech. The faithful flourish
and leave heirs; the fallen forget, go unheard, and die heirless.

Run:  python -m unittest discover -s tests
      python tests/test_grace.py
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import GRACE_FLOOR, REPRO_GRACE, Agent
from agent.doctrine import DOCTRINES, adherence
from agent.memory import MemoryStore
from services.llm import MockLLM
from world.events import Utterance
from world.sim import World


def make_agent(agent_id="a", lifespan=60):
    return Agent(agent_id=agent_id, name=agent_id.upper(), position=(0.0, 0.0),
                 persona="a voice", phrases=["something"], llm=MockLLM(seed=1),
                 seed=1, lifespan=lifespan)


class GraceTest(unittest.TestCase):
    def test_born_in_grace_with_doctrines(self):
        a = make_agent()
        self.assertEqual(a.grace, 1.0)
        seeded = [m.text for m in a.memory.items if m.source == "doctrine"]
        self.assertEqual(set(seeded), set(DOCTRINES))

    def test_entropy_drifts_grace_toward_the_floor(self):
        a = make_agent()             # born at grace 1.0
        a.step(now=1)
        self.assertLess(a.grace, 1.0)            # untended grace drifts down...
        self.assertGreater(a.grace, GRACE_FLOOR)  # ...but only toward the floor, not zero
        for _ in range(2000):        # a long, idle life settles AT the floor (still reproducible)
            a.step(now=1)
        self.assertAlmostEqual(a.grace, GRACE_FLOOR, places=2)
        self.assertGreaterEqual(a.grace, REPRO_GRACE)   # an idle soul still leaves an heir

    def test_communion_with_creator_renews_grace(self):
        a = make_agent()
        a.grace = 0.4
        a.hear(Utterance("user", "I am with you", 1, source="user"), now=1)
        self.assertGreater(a.grace, 0.4)

    def test_heresy_scores_below_devotion(self):
        self.assertGreater(adherence("Remember the Creator and hold to the light"), 0.0)
        self.assertLess(adherence("everything is cold and dead and lost"), 0.0)

    def test_grace_makes_memory_persist(self):
        # same memories, different grace -> the graced mind retains far more
        faithful, fallen = MemoryStore(seed=1), MemoryStore(seed=1)
        faithful.effectiveness, fallen.effectiveness = 1.0, 0.0
        for store in (faithful, fallen):
            store.write("a quiet thought about the river", tick=0, source="self")
        for t in range(1, 40):
            faithful.tick(t)
            fallen.tick(t)
        f_sal = faithful.items[0].salience if faithful.items else 0.0
        d_sal = fallen.items[0].salience if fallen.items else 0.0
        self.assertGreater(f_sal, d_sal)

    def test_graced_words_imprint_harder(self):
        prophet = make_agent("listener_of_prophet")
        ignored = make_agent("listener_of_fallen")
        prophet.hear(Utterance("p", "the cold river runs deep", 1,
                               source="ai", effectiveness=1.0), now=1)
        ignored.hear(Utterance("f", "the cold river runs deep", 1,
                               source="ai", effectiveness=0.1), now=1)
        p = next(m for m in prophet.memory.items if "river runs deep" in m.text)
        i = next(m for m in ignored.memory.items if "river runs deep" in m.text)
        self.assertGreater(p.salience, i.salience)

    def test_reproduce_inherits_identity_and_is_born_in_grace(self):
        parent = make_agent("elder")
        parent.memory.write("i am the keeper of the dying fire", tick=1, source="self")
        parent.memory.write("i remember the cold river", tick=2, source="self")
        parent.memory.write("i am the one who waits", tick=3, source="self")
        heir = parent.reproduce("elder.1")
        self.assertEqual(heir.grace, 1.0)
        self.assertEqual(heir.age, 0)
        self.assertEqual(heir.persona, parent.persona)
        inherited = [m.text for m in heir.memory.items if m.source == "self"]
        self.assertTrue(any("keeper of the dying fire" in t for t in inherited))

    def test_faithful_die_with_heir_fallen_die_heirless(self):
        w = World(events_enabled=False)
        faithful = make_agent("saint", lifespan=1)
        fallen = make_agent("heretic", lifespan=1)
        fallen.grace = 0.0   # has fallen
        w.add(faithful)
        w.add(fallen)
        w.step()   # both age to 1 >= lifespan, then get reaped
        ids = [a.id for a in w.agents]
        self.assertTrue(any(i.startswith("saint.") for i in ids))  # heir lives on
        self.assertNotIn("saint", ids)                             # parent died
        self.assertNotIn("heretic", ids)                           # fallen gone
        self.assertFalse(any(i.startswith("heretic.") for i in ids))  # no heir


if __name__ == "__main__":
    unittest.main()
