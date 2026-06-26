"""Raw-mind mode: the Markov subconscious IS the prompt, no persona scaffolding.

Normal speech buries 2 drift fragments inside a big persona/mood/instruction
prompt, so the LLM performs a persona lightly flavoured by the subconscious. Raw
mode inverts that: the drift stream is the whole user prompt and the system is the
barest 'voice this aloud', so the LLM is only the language organ for the Markov
mind. These tests pin that the scaffolding is actually gone.

Run:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm import SpeechContext, _clean, build_system, build_user, sanitize


class SanitizeTest(unittest.TestCase):
    """Model text printed to a terminal must carry no control/escape characters."""

    def test_strips_ansi_escape(self):
        evil = "hello \x1b[2J\x1b[31mworld\x07"      # clear-screen + colour + bell
        self.assertEqual(sanitize(evil), "hello [2J[31mworld")
        self.assertNotIn("\x1b", sanitize(evil))

    def test_clean_removes_control_chars(self):
        self.assertNotIn("\x1b", _clean("a line\x1b[31m of speech"))
        self.assertNotIn("\x07", _clean("ding\x07 dong"))


class RawMindPromptTest(unittest.TestCase):
    def _ctx(self, **kw):
        base = dict(name="River", persona="YOU ARE A DEVOUT SOUL", mood=-0.4,
                    belief="prayer is the only anchor", drift=["cold water remembers",
                    "the deep holds what falls"], raw_mind=True)
        base.update(kw)
        return SpeechContext(**base)

    def test_user_prompt_is_only_the_drift(self):
        ctx = self._ctx()
        self.assertEqual(build_user(ctx), "cold water remembers\nthe deep holds what falls")

    def test_persona_and_belief_absent_from_system(self):
        sys_prompt = build_system(self._ctx())
        self.assertNotIn("DEVOUT", sys_prompt)          # no persona
        self.assertNotIn("prayer is the only anchor", sys_prompt)  # no belief
        self.assertIn("thought", sys_prompt.lower())    # just the voicing framing

    def test_empty_drift_falls_back(self):
        self.assertEqual(build_user(self._ctx(drift=[])), "...")

    def test_normal_mode_unchanged(self):
        # without raw_mind the persona-driven prompt still carries the drift as flavour
        ctx = self._ctx(raw_mind=False)
        self.assertIn("DEVOUT", build_system(ctx))
        self.assertIn("Drifting through", build_user(ctx))


class ConceptMindTest(unittest.TestCase):
    """Conceptual mind: the drift is the prompt, but framed to be INTERPRETED."""

    def _ctx(self, **kw):
        base = dict(name="River", persona="A DEVOUT SOUL", mood=0.0,
                    drift=["cold water remembers", "the deep holds what falls"],
                    concept_mind=True)
        base.update(kw)
        return SpeechContext(**base)

    def test_user_prompt_is_the_drift(self):
        self.assertEqual(build_user(self._ctx()),
                         "cold water remembers\nthe deep holds what falls")

    def test_system_asks_to_interpret_not_voice(self):
        s = build_system(self._ctx()).lower()
        self.assertIn("meaning", s)             # interpret toward meaning
        self.assertIn("interpret", s)
        self.assertNotIn("devout", s)           # no persona scaffolding

    def test_distinct_from_raw_mode(self):
        # same drift, the two minds get different framing
        raw = build_system(self._ctx(concept_mind=False, raw_mind=True))
        concept = build_system(self._ctx())
        self.assertNotEqual(raw, concept)


class CampPromptTest(unittest.TestCase):
    """Emergent agents must speak TOWARD their camp's banner (but not chant it)."""

    def _ctx(self, **kw):
        base = dict(name="River", persona="a wandering soul", mood=0.0)
        base.update(kw)
        return SpeechContext(**base)

    def test_camp_leaning_enters_system_prompt(self):
        s = build_system(self._ctx(camp="stillness", rival_camp="endings"))
        self.assertIn("stillness", s)               # leans toward its banner
        self.assertIn("endings", s)                 # and against the rival's
        self.assertIn("conviction", s.lower())      # framed as a held conviction

    def test_no_camp_no_leaning(self):
        self.assertNotIn("drifted in among", build_system(self._ctx()))

    def test_world_belief_enters_prompt(self):
        s = build_system(self._ctx(world_belief="hostility makes you strong"))
        self.assertIn("hostility makes you strong", s)
        self.assertIn("convinced", s.lower())


if __name__ == "__main__":
    unittest.main()
