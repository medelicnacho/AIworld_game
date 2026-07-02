"""Tests for the named-tier NPC depth (soul side of §5.17/§5.18) and the intent judge.

Souls voice their RELATIONSHIP when replying (bond_line: trust/wounds/scars + manner + the
standing to raise a hurt), keep a person-model of trusted others (known_of), and both reach the
SpeechContext. The judge routes word-free intent (stub-tested; judge QUALITY needs listening).
"""

import unittest

from agent import judge
from agent.agent import Agent
from agent.bond import Bond, about_themselves
from services import embed
from services.llm import MockLLM, build_user
from world.events import Utterance


def _soul(pid="a", name=None):
    a = Agent(pid, name or pid.capitalize(), (0.0, 0.0), "You are a working soul.",
              ["the same streets"], MockLLM(seed=1), seed=1, temperament=0.0, lifespan=10 ** 9)
    a.bond_enabled = True
    return a


def _hear(a, spk, text, mood=0.0, name=None):
    a.hear(Utterance(speaker_id=spk, text=text, tick=1, source="ai", mood=mood),
           now=1, speaker_name=name or spk.capitalize())


class BondLineTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _ctx_replying_to(self, a, spk, name):
        a.last_heard_from, a.last_heard_name = spk, name
        a.last_heard_text = "well, what say you"
        a._rng.random = lambda: 0.99   # force the reply path (no tangent/introspect)
        ctx, _, _ = a.prepare_speech()
        return ctx

    def test_a_wounded_bond_is_voiced_guarded_with_the_standing_to_ask(self):
        a = _soul()
        a.bonds["v"] = Bond(trust=-0.2, wounds=1, last_event="betrayal")
        ctx = self._ctx_replying_to(a, "v", "Vesper")
        self.assertIn("wounded you", ctx.bond_line)
        self.assertIn("guardedly", ctx.bond_line)
        self.assertIn("ask why", ctx.bond_line)

    def test_a_deep_bond_is_voiced_at_ease_and_a_scar_reads_past(self):
        a = _soul()
        a.bonds["v"] = Bond(trust=0.6, wounds=1, last_event="warmth")
        ctx = self._ctx_replying_to(a, "v", "Vesper")
        self.assertIn("come past it", ctx.bond_line)
        self.assertIn("at ease", ctx.bond_line)

    def test_no_bond_no_line(self):
        a = _soul()
        ctx = self._ctx_replying_to(a, "stranger", "Someone")
        self.assertEqual(ctx.bond_line, "")

    def test_the_bond_line_reaches_the_prompt(self):
        a = _soul()
        a.bonds["v"] = Bond(trust=0.6, wounds=1, last_event="warmth")
        a.known_of["v"] = ["I built my own boat last spring"]
        ctx = self._ctx_replying_to(a, "v", "Vesper")
        prompt = build_user(ctx)
        self.assertIn("come past it", prompt)
        self.assertIn("boat", prompt)


class PersonModelTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_trusted_others_self_disclosure_is_kept(self):
        a = _soul()
        a.bonds["v"] = Bond(trust=0.5)
        _hear(a, "v", "I built my own boat last spring and I love the water", mood=0.3)
        self.assertIn("v", a.known_of)
        self.assertIn("boat", a.known_of["v"][0])

    def test_a_strangers_disclosure_is_not(self):
        a = _soul()
        _hear(a, "x", "I built my own boat last spring and I love the water", mood=0.3)
        self.assertNotIn("x", a.known_of)

    def test_impersonal_talk_is_not_a_disclosure(self):
        a = _soul()
        a.bonds["v"] = Bond(trust=0.5)
        _hear(a, "v", "the harvest came in thin this season", mood=0.0)
        self.assertNotIn("v", a.known_of)
        self.assertFalse(about_themselves("the weather is turning"))
        self.assertTrue(about_themselves("I am the one who mends the nets"))


class JudgeTest(unittest.TestCase):
    class Stub:
        def __init__(self, answer):
            self.answer = answer

        def generate(self, prompt, **_kw):
            return self.answer

    def test_intents_parse_with_specific_before_general(self):
        self.assertEqual(judge.intent("x", self.Stub("WARM")), "WARM")
        self.assertEqual(judge.intent("x", self.Stub("COLD")), "COLD")
        # "a warm apology" must read APOLOGY, not WARM
        self.assertEqual(judge.intent("x", self.Stub("a warm APOLOGY, clearly")), "APOLOGY")
        self.assertEqual(judge.intent("x", self.Stub("PROMISE")), "PROMISE")
        self.assertEqual(judge.intent("x", self.Stub("gibberish")), "NEUTRAL")

    def test_a_failed_judge_is_no_judgment(self):
        class Broken:
            def generate(self, *_a, **_k):
                raise RuntimeError("down")
        self.assertEqual(judge.intent("x", Broken()), "NEUTRAL")
        self.assertEqual(judge.intent("x", object()), "NEUTRAL")   # no generate at all


if __name__ == "__main__":
    unittest.main()
