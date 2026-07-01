"""Tests for expectation -- the self's future tense (agent/expectation.py).

Deterministic substrate checks (MockLLM, Jaccard-only). Expectation must: stay OFF by default
(regression), track lived mood fast/slow, appraise the SAME event differently by what was expected
(shock vs resignation vs relief), spike-and-settle arousal, read a violated conduct-expectation as
betrayal (a wound) while the same act from one expected cold is mere weather, and turn the
self-model load-bearing (out-of-character conduct -> dissonance -> a TURNING memory that enters
identity recall) -- firing on a real shift, never on noise, never with the faculty off.
"""

import unittest

from agent import expectation, psyche
from agent.agent import Agent
from agent.bond import Bond
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent


def _soul(expect=True, temperament=0.0, pid="s"):
    a = Agent(pid, "Soul", (0.0, 0.0), "You are a working soul.", ["the same streets"],
              MockLLM(seed=1), seed=1, temperament=temperament, lifespan=10 ** 9)
    a.expect_enabled = expect
    return a


class DefaultOffTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_off_by_default_event_charge_unchanged(self):
        a = _soul(expect=False)
        ev = WorldEvent(name="loss", description="someone dear is gone", tick=1, emotion=-0.7)
        a.perceive(ev, now=1)
        m = next(m for m in a.memory.items if m.source == "event")
        self.assertEqual(m.emotion, -0.7)
        self.assertEqual(a.arousal, 0.0)
        self.assertEqual(a._turnings, 0)

    def test_foreboding_is_zero_when_disabled(self):
        a = _soul(expect=False)
        a.exp_fast, a.exp_slow = -0.5, 0.3    # even with a worsening trend on the fields
        self.assertEqual(expectation.foreboding(a), 0.0)


class ExpectationDynamicsTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_fast_tracks_mood_faster_than_slow(self):
        a = _soul()
        a.memory.write("the flood took everything", tick=1, source="event", emotion=-0.8)
        for t in range(2, 8):
            a.step(t)
        self.assertLess(a.exp_fast, a.exp_slow)      # the fast read has caught the fall first
        self.assertGreater(expectation.foreboding(a), 0.0)

    def test_no_foreboding_while_things_improve(self):
        a = _soul()
        a.memory.write("a warm bright festival day", tick=1, source="event", emotion=0.7)
        for t in range(2, 8):
            a.step(t)
        self.assertEqual(expectation.foreboding(a), 0.0)

    def test_arousal_spikes_on_surprise_and_settles(self):
        a = _soul()
        a.exp_fast = 0.4                              # things had been good
        expectation.appraise_event(a, -0.7)           # the blow lands out of nowhere
        self.assertGreater(a.arousal, 0.2)
        peak = a.arousal
        for t in range(1, 15):
            a.step(t)
        self.assertLess(a.arousal, peak * 0.5)        # a spike that settles, not a mood


class AppraisalTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_the_same_loss_lands_as_shock_or_resignation(self):
        braced, blindsided = _soul(pid="b"), _soul(pid="u")
        braced.exp_fast = -0.5                        # already living the grief
        blindsided.exp_fast = 0.4                     # things had been good
        shock = expectation.appraise_event(blindsided, -0.7)
        resigned = expectation.appraise_event(braced, -0.7)
        self.assertLess(shock, -0.7)                  # amplified beyond the raw charge
        self.assertGreater(resigned, -0.7)            # softened -- braced for it
        self.assertGreater(blindsided.arousal, braced.arousal)

    def test_an_unexpected_good_lands_brighter(self):
        weary, easy = _soul(pid="w"), _soul(pid="e")
        weary.exp_fast = -0.5
        easy.exp_fast = 0.5
        self.assertGreater(expectation.appraise_event(weary, 0.6),
                           expectation.appraise_event(easy, 0.6))


class ConductExpectationTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _feed(self, a, other, sig, times, start=0):
        b = a.bonds.setdefault(other, Bond())
        for i in range(times):
            expectation.appraise_conduct(a, other, "Vesper", sig, start + i, b)
        return b

    def test_a_cold_act_from_one_expected_warm_is_a_betrayal(self):
        a = _soul()
        a.bond_enabled = True
        b = self._feed(a, "v", 0.4, 12)               # a long warmth -> I expect it of them
        self.assertEqual(b.wounds, 0)
        expectation.appraise_conduct(a, "v", "Vesper", -0.4, 20, b)
        self.assertEqual(b.wounds, 1)                 # the violated expectation IS the injury
        self.assertTrue(any("did not see it coming" in m.text for m in a.memory.items))

    def test_the_same_cold_act_from_one_expected_cold_is_weather(self):
        a = _soul()
        a.bond_enabled = True
        b = self._feed(a, "v", -0.2, 12)              # I expected nothing good of them
        expectation.appraise_conduct(a, "v", "Vesper", -0.4, 20, b)
        self.assertEqual(b.wounds, 0)

    def test_an_unexpected_kindness_from_one_expected_cold_warms(self):
        a = _soul()
        a.bond_enabled = True
        b = self._feed(a, "v", -0.3, 12)
        t0 = b.trust
        expectation.appraise_conduct(a, "v", "Vesper", 0.5, 20, b)
        self.assertGreater(b.trust, t0)
        self.assertTrue(any("unexpected kindness" in m.text for m in a.memory.items))


class TurningPointTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _live(self, a, actions):
        for t, act in enumerate(actions, start=1):
            a._last_action = act
            a.step(t)

    def test_a_sustained_conduct_flip_turns_the_self_once(self):
        a = _soul()
        self._live(a, ["share"] * 60 + ["hoard"] * 60)
        self.assertEqual(a._turnings, 1)
        turning = [m for m in a.memory.items if m.source == "turning"]
        self.assertEqual(len(turning), 1)
        self.assertIn("something in me has turned", turning[0].text)
        self.assertIn("shared and tended", turning[0].text)   # it names who I WAS
        # the chapter-break enters identity recall alongside the self-statements
        self.assertIn(turning[0].text, [m.text for m in a.memory.recall_self(k=3)])

    def test_stable_conduct_with_noise_never_turns(self):
        a = _soul()
        acts = (["share"] * 9 + ["work"]) * 12        # steady self, ordinary variation
        self._live(a, acts)
        self.assertEqual(a._turnings, 0)
        self.assertLess(a.self_dissonance, 0.5)       # far from a turning

    def test_no_turning_with_the_faculty_off(self):
        a = _soul(expect=False)
        self._live(a, ["share"] * 60 + ["hoard"] * 60)
        self.assertEqual(a._turnings, 0)


class LiveWorldWiringTest(unittest.TestCase):
    """Expectation is ON for the living town (genesis souls) and the stakes hardships --
    the town's main blows -- route through appraisal, so shock/resignation happen live."""

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_genesis_soul_wakes_expecting(self):
        from agent import genesis
        a = _soul(expect=False)
        genesis.endow_faculties(a, a._rng)
        self.assertTrue(a.expect_enabled)

    def test_a_hardship_shocks_the_easy_and_spares_the_braced(self):
        from world import stakes
        from world.sim import World
        w = World(events_enabled=False)
        easy, braced = _soul(pid="e"), _soul(pid="b")
        easy.exp_fast, braced.exp_fast = 0.4, -0.5
        for a in (easy, braced):
            w.add(a)
        stakes.hardship(w, [easy, braced], now=5, kind="flood")
        def charge(a):
            return next(m.emotion for m in a.memory.items if "took my provisions" in m.text)
        self.assertLess(charge(easy), charge(braced))    # same flood, harder on the blindsided


class PsycheConfigPinTest(unittest.TestCase):
    """The psyche keeps its §5.14 configuration: the expectation port was tried and
    REVERTED (PREDICTION stayed 0/5 held-out and STRUCTURE degraded -- FINDINGS §5.15).
    These pins keep the reverted coupling from silently returning."""

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_endow_part_leaves_expectation_off(self):
        d = Agent("d", "Dread", (0.0, 0.0), "a part of one mind", ["what if"],
                  MockLLM(seed=1), seed=1, temperament=-0.5, lifespan=10 ** 9)
        psyche.endow_part(d, "grip", d._rng)
        self.assertFalse(d.expect_enabled)

    def test_dreads_bid_ignores_the_trend(self):
        def dread_with_trend(fast, slow, pid):
            d = Agent(pid, "Dread", (0.0, 0.0), "a part of one mind", ["what if"],
                      MockLLM(seed=1), seed=1, temperament=-0.5, lifespan=10 ** 9)
            psyche.endow_part(d, "grip", d._rng)
            d.exp_fast, d.exp_slow = fast, slow
            return d
        worsening = dread_with_trend(-0.4, 0.1, "d1")
        steady = dread_with_trend(0.1, 0.1, "d2")
        self.assertEqual(psyche.activation(worsening, [worsening], now=100),
                         psyche.activation(steady, [steady], now=100))


if __name__ == "__main__":
    unittest.main()
