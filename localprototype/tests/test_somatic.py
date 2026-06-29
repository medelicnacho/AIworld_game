"""Tests for the somatic interrupt (agent/somatic.py + experiment_somatic.py).

Deterministic substrate checks (MockLLM, Jaccard-only so self-relevance is by origin). The interrupt is
a bottom-up circuit-breaker on the second-arrow spiral: it must BOUND a runaway, RECOVER (re-expand,
not stay numb), leave a single FIRST arrow felt, scale with the grip (so only a clinging soul spirals),
and stay OFF by default.
"""

import unittest

from agent import somatic
from agent.agent import Agent
from services import embed
from services.llm import MockLLM
import experiment_somatic as es


def _clinging_agent(somatic_on=True, grip=0.85, prajna=0.05):
    a = Agent("self", "Soul", (0.0, 0.0), "You are a working soul.", ["the same streets"],
              MockLLM(seed=1), seed=1, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = grip, prajna, True
    a.transmute = a.self_liberation = 0.0
    a.somatic_enabled = somatic_on
    return a


class SpiralMetricTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_metric_scales_with_grip_only_a_clinging_soul_spirals(self):
        # identical aversive memory, different grip -> the amplifier (effective grip) sets the spiral.
        clinging = _clinging_agent(grip=0.85, prajna=0.05)
        easeful = _clinging_agent(grip=0.30, prajna=0.70)
        for a in (clinging, easeful):
            a.memory.write("I lost someone I loved", tick=0, source="self", speaker_id="self", emotion=-0.85)
        self.assertGreater(somatic.spiral_metric(clinging), somatic.spiral_metric(easeful))

    def test_aversive_load_ignores_pleasant_and_doctrine(self):
        a = _clinging_agent()
        a.memory.items.clear()
        a.memory.write("a warm bright day", tick=0, source="self", speaker_id="self", emotion=0.6)
        self.assertEqual(somatic.aversive_load(a), 0.0)
        a.memory.write("I lost someone I loved", tick=0, source="self", speaker_id="self", emotion=-0.8)
        self.assertGreater(somatic.aversive_load(a), 0.0)


class InterruptDynamicsTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_single_first_arrow_is_felt_not_interrupted(self):
        # one sharp loss, no sustained rise -> the spiral never builds, the interrupt never fires.
        a = _clinging_agent(somatic_on=True)
        a.memory.write("I lost someone I loved", tick=1, source="self", speaker_id="self", emotion=-0.85)
        for t in range(2, 18):
            a.step(t)
        self.assertEqual(a._somatic_trips, 0)
        self.assertEqual(a._contraction, 0.0)

    def test_off_by_default_has_no_effect(self):
        # somatic disabled -> never contracts, manas behaves exactly as before (a regression guard).
        on = es.run(somatic_on=True, config="clinging")
        off = es.run(somatic_on=False, config="clinging")
        self.assertEqual(off["trips"], 0)
        self.assertTrue(all(c == 0.0 for c in off["contr"]))
        self.assertGreater(on["trips"], 0)   # ... whereas with it on, it actually fires


class RunawayFalsifierTest(unittest.TestCase):
    """The headline: with top-down DHARMA disabled, only the bottom-up interrupt can break the spiral."""

    def setUp(self):
        embed.use_jaccard_only(True)
        self.off = es.run(somatic_on=False, config="clinging")
        self.on = es.run(somatic_on=True, config="clinging")
        self.healthy = es.run(somatic_on=True, config="healthy")

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_without_the_interrupt_the_wound_diverges_and_is_held(self):
        # the clinging soul's lived mood sinks and the grip holds it through the quiet phase.
        self.assertLess(self.off["mood"][es.QUIET_UNTIL - 1], -0.4)

    def test_the_interrupt_bounds_the_spiral_and_recovers(self):
        on_recovered = self.on["mood"][es.QUIET_UNTIL - 1]
        off_recovered = self.off["mood"][es.QUIET_UNTIL - 1]
        on_trough = min(self.on["mood"][:es.LOSS_PHASE])
        self.assertGreater(self.on["trips"], 0)                      # it actually fired
        self.assertGreater(on_recovered, off_recovered + 0.2)        # bounded where off stays wounded
        self.assertGreater(on_recovered, on_trough + 0.15)           # re-expanded (recovery)
        self.assertLess(self.on["contr"][es.QUIET_UNTIL - 1], 0.10)  # contraction returned to open

    def test_a_fresh_first_arrow_after_recovery_still_registers(self):
        # the window of tolerance, not a numb setpoint: a new loss still dips the mood.
        pre = self.on["mood"][es.FRESH_LOSS_TICK - 2]
        post = self.on["mood"][es.FRESH_LOSS_TICK]
        self.assertLess(post, pre - 0.05)

    def test_rare_backstop_a_healthy_regime_never_trips(self):
        self.assertEqual(self.healthy["trips"], 0)


if __name__ == "__main__":
    unittest.main()
