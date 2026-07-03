"""Tests for the affinity ledger (rung 1): the substrate factions form on.

An agent stores no social graph. It accretes a feeling toward each other agent
from whether that agent has shared its emotional reality. Same-signed feeling
(both dark, both bright) bonds; opposed signs divide; neutral barely moves it.
Plus the self-anti-echo buffer that stops a small local model looping on its
own line.

Run:  python -m unittest discover -s tests
      python tests/test_affinity.py
"""

from __future__ import annotations

import unittest


from agent.agent import Agent
from services.llm import MockLLM
from world.events import Utterance


def make_agent(agent_id="a"):
    return Agent(agent_id=agent_id, name=agent_id.upper(), position=(0.0, 0.0),
                 persona="a voice", phrases=["something"], llm=MockLLM(seed=1), seed=1)


class AffinityTest(unittest.TestCase):
    def test_shared_darkness_bonds(self):
        a = make_agent()
        # give A a dark stance of its own (affinity needs the listener to have one)
        a.memory.write("cold dark empty death", tick=0, source="self")
        self.assertLess(a.felt_mood(), 0.0)
        # a speaker of like (dark) disposition -> kinship
        a.hear(Utterance("b", "everything is cold and lost", 1, source="ai", mood=-0.6), now=1)
        self.assertGreater(a.feels_about("b"), 0.0)   # shared disposition -> kin

    def test_opposed_feeling_divides(self):
        a = make_agent()
        a.memory.write("cold dark empty death", tick=0, source="self")
        # a speaker of opposite (bright) disposition -> enmity
        a.hear(Utterance("c", "warm bright hope love light", 1, source="ai", mood=0.6), now=1)
        self.assertLess(a.feels_about("c"), 0.0)      # opposed disposition -> foe

    def test_neutral_listener_forms_no_opinion(self):
        a = make_agent()   # disposition ~0, no stance yet
        a.hear(Utterance("b", "warm bright hope", 1, source="ai", mood=0.6), now=1)
        self.assertAlmostEqual(a.feels_about("b"), 0.0, places=6)

    def test_unknown_agent_is_neutral(self):
        self.assertEqual(make_agent().feels_about("nobody"), 0.0)

    def test_strong_feeling_pulls_harder_when_addressed(self):
        a = make_agent()
        a.affinity["b"] = 0.8                          # strong feeling about B
        before = a.speak_urge
        a.hear(Utterance("b", "hey you", 1, addressed_to="a", source="ai"), now=1)
        strong_pull = a.speak_urge - before

        n = make_agent()                               # no feeling about B
        before2 = n.speak_urge
        n.hear(Utterance("b", "hey you", 1, addressed_to="a", source="ai"), now=1)
        weak_pull = n.speak_urge - before2
        self.assertGreater(strong_pull, weak_pull)

    def test_self_echo_buffer_records_own_lines(self):
        a = make_agent()
        for _ in range(5):
            a.speak(now=1)
        self.assertLessEqual(len(a.spoken), 3)         # trimmed to SELF_ECHO
        self.assertTrue(all(isinstance(s, str) for s in a.spoken))


if __name__ == "__main__":
    unittest.main()
