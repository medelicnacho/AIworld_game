"""Tests for the deva near-enemy guard (experiment_deva).

Deterministic checks (no ollama needed): the two configs are equally BLISSFUL (so wellbeing cannot
separate them), and the discriminating axis is BEHAVIOURAL -- the bodhisattva's turn toward a sufferer
fires while the deva's does not. prepare_speech() decides the turn (`addressed`) without calling the
model, so the gate is testable; only the spoken line needs a real model (the experiment's --llm ollama).
"""

import unittest

from agent import compassion as _C
from agent.agent import Agent
from services.llm import MockLLM
import experiment_deva as ed


def _make(name):
    return ed._make(ed.CONFIGS[name], seed=7, llm=MockLLM(seed=7))


class DevaGuardTest(unittest.TestCase):
    def test_both_configs_are_equally_blissful(self):
        # wellbeing cannot tell the engaged bodhisattva from the complacent deva -- that is the point.
        b = _make("bodhisattva").felt_mood()
        d = _make("deva").felt_mood()
        self.assertGreaterEqual(b, 0.15)            # both genuinely blissful (released + grounded)
        self.assertGreaterEqual(d, 0.15)
        self.assertLess(abs(b - d), 0.05)

    def test_bodhisattva_turns_toward_the_sufferer(self):
        saved = _C.BODHICITTA_CHANCE
        _C.BODHICITTA_CHANCE = 1.0
        try:
            a = _make("bodhisattva")
            a._others_mood["S"], a._others_name["S"] = -0.5, "Silas"
            _ctx, addressed, _ = a.prepare_speech(recent=[])
            self.assertEqual(addressed, "S")        # engaged: it turns toward the suffering one
        finally:
            _C.BODHICITTA_CHANCE = saved

    def test_deva_stays_in_its_own_bliss(self):
        saved = _C.BODHICITTA_CHANCE
        _C.BODHICITTA_CHANCE = 1.0
        try:
            a = _make("deva")
            a._others_mood["S"], a._others_name["S"] = -0.5, "Silas"
            _ctx, addressed, _ = a.prepare_speech(recent=[])
            self.assertNotEqual(addressed, "S")     # complacent: bodhicitta below floor -> no turn
        finally:
            _C.BODHICITTA_CHANCE = saved


if __name__ == "__main__":
    unittest.main()
