"""The signed-stance affinity fix: opposed leans must SOUR a bond, aligned ones
WARM it -- the recoil-on-disagreement the sign-less lexical space could not do."""

import random
import unittest

from agent import stance
from agent.agent import Agent
from services.llm import MockLLM
from world.events import Utterance


def _agent(aid, vec=None):
    a = Agent(aid, aid, (0.0, 0.0), "", ["a line"], MockLLM(seed=1), seed=1)
    if vec is not None:
        a.stance_vec = stance._normalize(list(vec))
    return a


def _utter(speaker):
    return Utterance(speaker_id=speaker.id, text="whatever they said", tick=1,
                     source="ai", stance_vec=tuple(speaker.stance_vec))


class StanceModule(unittest.TestCase):
    def test_seed_is_unit_and_independent(self):
        v = stance.seed(random.Random(1))
        self.assertEqual(len(v), stance.DIM)
        self.assertAlmostEqual(sum(x * x for x in v) ** 0.5, 1.0, places=6)
        self.assertNotEqual(stance.seed(random.Random(1)), stance.seed(random.Random(2)))

    def test_describe_names_the_leant_pole(self):
        v = [0.0] * stance.DIM
        v[0] = 1.0   # full lean to axis 0's positive pole ("mastery")
        self.assertIn("mastery over surrender", stance.describe(v))
        v[0] = -1.0
        self.assertIn("surrender over mastery", stance.describe(v))

    def test_ground_pulls_toward_spoken_pole(self):
        v = [0.0] * stance.DIM
        moved = stance.ground(v, "we must conquer and master and force it")
        self.assertGreater(moved[0], 0.0)            # mastery words pull +
        moved2 = stance.ground(v, "yield, accept, find harmony, surrender")
        self.assertLess(moved2[0], 0.0)              # surrender words pull -

    def test_ground_noop_without_pole_words(self):
        v = stance._normalize([0.3, -0.2, 0.5, 0.1, -0.4])
        self.assertEqual(stance.ground(v, "the the the and of"), v)


class StanceAffinity(unittest.TestCase):
    def test_opposed_stance_sours_the_bond(self):
        a = _agent("a", [1, 0, 0, 0, 0])
        foe = _agent("foe", [-1, 0, 0, 0, 0])   # exact opposite lean
        a.hear(_utter(foe), now=1)
        self.assertLess(a.affinity["foe"], 0.0)   # recoil: the missing sign at work

    def test_aligned_stance_warms_the_bond(self):
        a = _agent("a", [1, 0, 0, 0, 0])
        kin = _agent("kin", [1, 0, 0, 0, 0])      # same lean
        a.hear(_utter(kin), now=1)
        self.assertGreater(a.affinity["kin"], 0.0)

    def test_stance_takes_precedence_over_lexical(self):
        # a soul with BOTH a lexical belief_vec and a stance_vec bonds on stance
        a = _agent("a", [1, 0, 0, 0, 0])
        a.seed_opinion_text("baker dawn batch loaves")   # also give it a lexical vec
        foe = _agent("foe", [-1, 0, 0, 0, 0])
        a.hear(_utter(foe), now=1)
        self.assertLess(a.affinity["foe"], 0.0)   # stance (opposed) won, not lexical

    def test_legacy_soul_without_stance_unaffected(self):
        # no stance_vec, no belief_vec -> the old faith/disposition path still runs
        a = _agent("a")
        self.assertIsNone(a.stance_vec)
        b = _agent("b")
        u = Utterance(speaker_id="b", text="hi", tick=1, source="ai", mood=0.5)
        a.temperament = 0.5
        a.hear(u, now=1)   # must not raise; legacy disposition bonding
        self.assertIn("b", a.affinity)


if __name__ == "__main__":
    unittest.main()
