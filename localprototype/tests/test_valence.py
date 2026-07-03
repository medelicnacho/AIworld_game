"""Tests for the emotion sensor (valence): it must hear the agents' vocabulary.

The original lexicon only matched exact seed words, so ~86% of the local model's
lines registered no emotion. These assert the upgraded sensor handles inflections
(colder/ends/fading), negation (no warmth, not alone), and intensifiers, and that
coverage on real gemma3:4b output jumps well above the old 14%.

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_valence.py
"""

from __future__ import annotations

import unittest

# allow `python tests/test_valence.py` from anywhere

from agent.memory import valence


class ValenceTest(unittest.TestCase):
    def test_inflected_words_now_register(self):
        # base words the old sensor missed because only 'cold'/'end' were listed
        self.assertLess(valence("It feels colder now."), 0.0)
        self.assertLess(valence("It always ends like this."), 0.0)
        self.assertLess(valence("everything is fading away"), 0.0)
        self.assertGreater(valence("the light is brighter now"), 0.0)

    def test_negation_flips_polarity(self):
        self.assertLess(valence("there is no warmth here"), 0.0)   # pos word, negated
        self.assertGreater(valence("we are not alone anymore"), 0.0)  # neg word, negated
        self.assertLess(valence("never any hope left"), 0.0)

    def test_intensifier_increases_magnitude(self):
        self.assertLess(valence("really cold"), valence("cold"))
        self.assertGreater(valence("so warm"), 0.0)

    def test_plain_lines_stay_neutral(self):
        self.assertEqual(valence("the current pulls, a slow return"), 0.0)
        self.assertEqual(valence("dust motes shimmer in the air"), 0.0)

    def test_polarity_direction_and_bounds(self):
        self.assertGreater(valence("warm light, hope, and love"), 0.0)
        self.assertLess(valence("cold, dead, empty, lost"), 0.0)
        for t in ["warm warm warm", "cold dead empty broken hopeless"]:
            self.assertLessEqual(abs(valence(t)), 0.8 + 1e-9)

    def test_coverage_on_real_local_output(self):
        # the 14 lines gemma3:4b actually produced in the assessment run
        lines = [
            "The current pulls, a slow return.",
            "That’s convenient, isn't it?",
            "Is this flicker actually me?",
            "It feels colder now.",
            "Wait colder? Like, really colder? Does that even matter now?",
            "it settles deeper.",
            "Don’t bother. It always ends like this.",
            "Wait deeper? Is it gone completely?",
            "Dust motes they shimmer, do they even exist?",
            "Just another shimmer, I suppose.",
            "Is a shadow truly empty, or just waiting?",
            "The water remembers more than we do.",
            "Another pointless flicker. Let’s go.",
            "Is it pulling me again? The water remembers really?",
        ]
        hits = sum(1 for l in lines if valence(l) != 0.0)
        # old sensor: 2/14 (14%). Require a clear jump.
        self.assertGreaterEqual(hits, 5, f"expected >=5 lines to register, got {hits}")


if __name__ == "__main__":
    unittest.main()
