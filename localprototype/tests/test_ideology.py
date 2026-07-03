"""Tests for emergent ideology (rung 3): beliefs that form, convert, and clash.

A belief is just the thing an agent keeps saying (its salient self-statement),
so it emerges, hardens, converts, and passes to heirs. Hearing a line on your
belief's topic: same disposition reinforces you; opposed disposition either
CONVERTS you (a trusted/graced voice + weak conviction) or makes you DIG IN,
souring affinity and accreting hostility toward open war.

Run:  python -m unittest discover -s tests
      python tests/test_ideology.py
"""

from __future__ import annotations

import unittest


from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.events import Utterance

# topic-matching is deterministic word-overlap here, not live embeddings, so the
# mechanics (clash/convert/war) are tested independently of a running Ollama.
embed.use_jaccard_only(True)


def mk(name="a", temp=-0.4):
    return Agent(name, name.title(), (0.0, 0.0), f"You are {name}.", ["the fire"],
                 MockLLM(seed=1), seed=1, temperament=temp)


class IdeologyTest(unittest.TestCase):
    def test_belief_seeds_from_theme_and_is_stable(self):
        a = mk()   # phrases=["the fire"]
        self.assertEqual(a.belief, "the fire")
        # merely speaking/remembering must NOT redefine the core belief --
        # only genuine conversion changes it (else nobody holds a line to fight over)
        a.memory.write("something else entirely now", tick=2, source="self")
        self.assertEqual(a.belief, "the fire")

    def test_same_disposition_hardens_conviction(self):
        a = mk(temp=-0.4)
        a.memory.write("the fire keeps us trapped in the cold", tick=1, source="self")
        before = a.conviction
        a.hear(Utterance("b", "the fire is a cruel trap in the dark", 2,
                         source="ai", mood=-0.6, effectiveness=0.5), now=2)
        self.assertGreater(a.conviction, before)   # like minds reinforce me

    def test_untrusted_clash_builds_hostility_to_war(self):
        a = mk(temp=-0.4)
        a.memory.write("the fire keeps us alive in the cold", tick=1, source="self")
        for t in range(2, 9):   # a disliked, low-grace foe hammering my belief
            a.hear(Utterance("foe", "the fire is a lie that keeps us trapped", t,
                             source="ai", mood=0.6, effectiveness=0.1), now=t)
        self.assertLess(a.feels_about("foe"), 0.0)
        self.assertTrue(a.is_at_war_with("foe"))

    def test_trusted_graced_persuader_converts_a_weak_belief(self):
        c = mk(temp=-0.4)
        c.memory.write("the fire keeps us trapped in the cold", tick=1, source="self")
        c.affinity["prophet"] = 0.8     # trusted
        c.conviction = 0.2              # weakly held
        before = c.belief
        c.hear(Utterance("prophet", "the fire is hope and warmth and life", 2,
                         source="ai", mood=0.7, effectiveness=1.0), now=2)
        self.assertNotEqual(c.belief, before)
        self.assertIn("hope", c.belief)

    def test_firm_conviction_resists_conversion(self):
        c = mk(temp=-0.4)
        c.memory.write("the fire keeps us trapped in the cold", tick=1, source="self")
        c.affinity["prophet"] = 0.8
        c.conviction = 0.95             # firmly held -> persuasion can't beat it
        before = c.belief
        c.hear(Utterance("prophet", "the fire is hope and warmth and life", 2,
                         source="ai", mood=0.7, effectiveness=0.5), now=2)
        self.assertEqual(c.belief, before)

    def test_challenge_is_offered_back_as_rebuttal_context(self):
        a = mk(temp=-0.4)
        a.memory.write("the fire keeps us alive in the cold", tick=1, source="self")
        a.conviction = 0.9              # won't convert -> will dig in and rebut
        a.hear(Utterance("foe", "the fire is a lie that keeps us trapped", 2,
                         source="ai", mood=0.6, effectiveness=0.1), now=2)
        self.assertIsNotNone(a.last_challenge)
        ctx, _addressed, _mood = a.prepare_speech()
        self.assertEqual(ctx.challenge, a.last_challenge)


if __name__ == "__main__":
    unittest.main()
