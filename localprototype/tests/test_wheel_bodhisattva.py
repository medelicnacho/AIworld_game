"""Tests for the bodhisattva wheel wired into the live World (step 3).

Unit checks on the production carry (agent/path.carry_practice, agent/telos.transmute_thirst), plus a
short LIVE-WHEEL integration: a clinging town, dying and reborn, drifts toward the liberated ground with
the tilt on, and merely resets to the endowment baseline with it off. Deterministic (MockLLM, Jaccard).
"""

import random
import unittest

from agent import path, telos
from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World


class CarryPracticeTest(unittest.TestCase):
    def test_tilt_fades_toward_the_liberated_ground(self):
        rng = random.Random(0)
        g, p, b = path.carry_practice(0.80, 0.10, 0.10, rng, tilt=1.0)
        self.assertLess(g, 0.80)     # grip eroded toward the liberated 0.10
        self.assertGreater(p, 0.10)  # prajñā toward 0.70
        self.assertGreater(b, 0.10)  # bodhicitta toward 0.70

    def test_no_tilt_fades_toward_the_neutral_mean(self):
        rng = random.Random(0)
        g, _, _ = path.carry_practice(0.80, 0.10, 0.10, rng, tilt=0.0)
        self.assertLess(g, 0.80)               # still erodes a little (toward neutral 0.50) ...
        self.assertGreater(g, 0.55)            # ... but does NOT head for the liberated ground

    def test_transmute_thirst_three_fates(self):
        gripped = telos.transmute_thirst(0.80, effective_grip=0.70, bodhicitta=0.10)
        arhat = telos.transmute_thirst(0.80, effective_grip=0.05, bodhicitta=0.10)
        bodhi = telos.transmute_thirst(0.80, effective_grip=0.05, bodhicitta=0.90)
        self.assertGreater(gripped, 0.80)      # the clenched fire escalates
        self.assertLess(arhat, 0.45)           # the fire goes out
        self.assertGreater(bodhi, arhat + 0.30)  # bodhicitta keeps it alive (the vow)


def _wheel(tilt_on, ticks=160, seed=1):
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, move_seed=seed)   # seed World._rng -> deterministic carry/coalesce
    w.llm = MockLLM(seed=seed)
    w.bardo_ticks = (2, 5)
    w.bodhisattva_wheel = tilt_on
    w.liberation_tilt = 1.0
    for i in range(4):
        a = Agent(f"s{i}", f"Soul{i}", (0.0, 0.0), "You are a working soul.",
                  ["I work my trade"], w.llm, seed=seed + i, temperament=0.0,
                  lifespan=rng.randint(12, 20))   # short lives -> fast turnover
        a.grip, a.prajna, a.bodhicitta = 0.70, 0.10, 0.20
        a.ground_enabled = True
        w.add(a)
    for t in range(1, ticks + 1):
        w.step()
    import statistics
    return (statistics.fmean(a.grip for a in w.agents),
            statistics.fmean(a.prajna for a in w.agents),
            statistics.fmean(a.bodhicitta for a in w.agents),
            w._births)


class LiveWheelTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_tilt_on_drifts_the_town_toward_the_bodhisattva_ground(self):
        g, p, b, births = _wheel(tilt_on=True)
        self.assertGreater(births, 4)     # the wheel actually turned over (souls died and were reborn)
        self.assertLess(g, 0.40)          # grip fell well below the clinging 0.70 start
        self.assertGreater(p, 0.45)       # prajñā rose toward the liberated ground
        self.assertGreater(b, 0.40)       # bodhicitta rose (toward the bodhisattva)

    def test_tilt_off_resets_to_ordinary_wholesome_no_drift(self):
        # the plain wheel re-rolls endow_faculties (grip 0.2-0.5, prajñā 0.4, bodhicitta 0.5) and does
        # NOT head for the liberated ground -- markedly less free than the tilted wheel.
        on_g, on_p, on_b, _ = _wheel(tilt_on=True)
        off_g, off_p, off_b, _ = _wheel(tilt_on=False)
        self.assertGreater(off_g, on_g + 0.05)
        self.assertGreater(on_p, off_p + 0.10)
        self.assertGreater(on_b, off_b + 0.05)


if __name__ == "__main__":
    unittest.main()
