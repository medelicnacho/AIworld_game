"""Tests for Santāna's OWN faculties + the bounded conversation (santana.py §5.17).

Deterministic substrate checks (MockLLM, Jaccard-only). She must: wake with the validated
selfhood stack (expectation/arousal/bond), appraise what she hears against her own state
(shock vs braced; betrayal = the violated expectation), keep the conversation INERT toward
the town, persist her inner state across save/load (and load pre-faculty snapshots cleanly),
and lose it all cleanly when feel_enabled is off (the off-switch / mechanism arm).
"""

import json
import os
import tempfile
import unittest

from agent.agent import Agent
from santana import Santana
from santana_app.state import load_mind, save_mind
from services import embed
from services.llm import MockLLM
from world.sim import World

WARM = "I am glad and grateful for you, you have done well and I love this place"
COLD = "you are worthless and broken and I am done with you"
DARK = "everything you hold is failing and the dark is coming for all of it"


def _mind(feel=True, with_soul=False):
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    if with_soul:
        w.add(Agent("s0", "Toll", (0.0, 0.0), "You are Toll.", ["the charter"],
                    MockLLM(seed=1), seed=1, lifespan=10 ** 9))
    m = Santana(w, MockLLM(seed=7))
    m.feel_enabled = feel
    return m


class FacultiesTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_she_wakes_with_the_stack(self):
        m = _mind()
        self.assertTrue(m.feel_enabled)
        self.assertEqual(m.user_bond.trust, 0.0)
        self.assertEqual(m.arousal, 0.0)

    def test_a_conversation_is_remembered_and_warms_the_bond(self):
        m = _mind()
        reply = m.converse(WARM)
        self.assertTrue(reply)
        self.assertTrue(any(mm.source == "user" for mm in m.memory.items))
        self.assertTrue(any(mm.source == "self" for mm in m.memory.items))
        self.assertGreater(m.user_bond.trust, 0.0)
        self.assertEqual(len(m.talk), 2)

    def test_a_cold_word_from_one_expected_warm_wounds_her(self):
        m = _mind()
        for _ in range(12):
            m.converse(WARM)
        self.assertEqual(m.user_bond.wounds, 0)
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 1)
        self.assertTrue(any("did not see it coming" in mm.text for mm in m.memory.items))

    def test_the_same_cold_word_after_a_cold_history_is_weather(self):
        m = _mind()
        for _ in range(12):
            m.converse(COLD)
        wounds_before = m.user_bond.wounds
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, wounds_before)   # expected nothing better

    def test_the_same_news_shocks_or_is_braced_for(self):
        bright, grim = _mind(), _mind()
        bright.exp_fast, grim.exp_fast = 0.4, -0.5
        for m in (bright, grim):
            m.hear_user(DARK)
        def charge(m):
            return next(mm.emotion for mm in m.memory.items if mm.text == DARK)
        self.assertLess(charge(bright), charge(grim))
        self.assertGreater(bright.arousal, grim.arousal)

    def test_the_off_switch_feels_nothing(self):
        m = _mind(feel=False)
        for _ in range(12):
            m.converse(WARM)
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 0)
        self.assertEqual(m.arousal, 0.0)

    def test_the_conversation_is_inert_toward_the_town(self):
        m = _mind(with_soul=True)
        soul = m.world.agents[0]
        before = len(soul.memory.items)
        m.converse(WARM)
        m.converse(COLD)
        self.assertEqual(len(soul.memory.items), before)


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_her_inner_state_survives_a_save_and_load(self):
        m = _mind()
        for _ in range(6):
            m.converse(WARM)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mind.json")
            save_mind(m, path)
            fresh = _mind()
            self.assertTrue(load_mind(fresh, path))
        self.assertAlmostEqual(fresh.user_bond.trust, m.user_bond.trust)
        self.assertEqual(fresh.user_bond.wounds, m.user_bond.wounds)
        self.assertAlmostEqual(fresh.exp_fast, m.exp_fast)
        self.assertEqual(fresh.talk, m.talk)
        self.assertIn("user", fresh._conduct_expect)

    def test_a_pre_faculty_snapshot_loads_cleanly(self):
        old = {"identity": "an old mind", "last": "", "said": [], "mt": 40,
               "lifetime": 1000.0, "deaths": 3,
               "memory": [{"text": "I lost Vesper", "salience": 0.8, "created_tick": 5,
                           "last_touched_tick": 5, "source": "event", "speaker_id": None,
                           "emotion": -0.6, "mutation_count": 0}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(old, f)
            m = _mind()
            self.assertTrue(load_mind(m, path))
        self.assertEqual(m.identity, "an old mind")
        self.assertEqual(m.user_bond.trust, 0.0)     # faculties default fresh
        self.assertEqual(m._deaths, 3)
        self.assertEqual(len(m.memory.items), 1)


if __name__ == "__main__":
    unittest.main()
