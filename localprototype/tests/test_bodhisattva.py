"""Tests for the toward-buddhahood mechanisms (experiment_bodhisattva).

Deterministic substrate checks (MockLLM, seeded RNG) on the two mechanisms built so far:
  1. the CARRY makes the wheel a path (practice transmigrates), and un-tilted it is symmetric;
  2. the buddha-nature TILT makes liberation the attractor -- clinging slips, a wholesome lean
     sticks -- so a hungry-ghost start drifts to the bodhisattva basin, with an honest limit.
"""

import random
import unittest

import experiment_bodhisattva as eb


class CarryVasanaTest(unittest.TestCase):
    """The bardo carry: where the vāsanā fades, and the tilt's asymmetry."""

    def test_untilted_fades_both_leans_toward_the_neutral_mean(self):
        # tilt=0: a high-grip (clinging) lean falls toward 0.5, a low-grip (free) lean rises toward 0.5
        # -- symmetric, both pulled to the samsaric mean from their own side.
        rng = random.Random(0)
        clinging, _ = eb.carry_vasana(0.90, 0.20, rng, tilt=0.0)
        rng = random.Random(0)
        freed, _ = eb.carry_vasana(0.20, 0.20, rng, tilt=0.0)
        self.assertLess(clinging, 0.90)   # clinging eroded downward toward 0.5
        self.assertGreater(freed, 0.20)   # the free lean drifted UP toward 0.5 (no tilt = no homecoming)

    def test_tilt_makes_clinging_slip_and_a_wholesome_lean_stick(self):
        # tilt=1 fades toward the liberated ground (grip 0.1). Clinging (0.9) is FAR from it so it
        # erodes hard toward freedom (slips); a wholesome lean (0.2) is near it so it barely moves
        # (sticks). The asymmetry is the whole tathāgatagarbha point.
        rng = random.Random(0)
        clinging_moved = 0.90 - eb.carry_vasana(0.90, 0.20, rng, tilt=1.0)[0]
        rng = random.Random(0)
        wholesome_moved = abs(0.20 - eb.carry_vasana(0.20, 0.20, rng, tilt=1.0)[0])
        self.assertGreater(clinging_moved, 0.05)                 # clinging genuinely slipped toward freedom
        self.assertGreater(clinging_moved, wholesome_moved + 0.05)  # ... far more than the wholesome lean stirred

    def test_tilt_pulls_prajna_up_not_down(self):
        # the liberated ground has high prajñā (0.7): a low-wisdom lean should rise toward it under tilt.
        rng = random.Random(0)
        _, prajna = eb.carry_vasana(0.90, 0.10, rng, tilt=1.0)
        self.assertGreater(prajna, 0.10)


class PathTransmigratesTest(unittest.TestCase):
    """Mechanism 1: carrying the cultivated lean turns the wheel into a path."""

    def test_carried_practice_frees_a_lineage_but_fresh_reroll_does_not(self):
        carried = eb.run_lineage(eb.PRACTICE_SIGNAL, gens=6, carry=True, seed=1)
        fresh = eb.run_lineage(eb.PRACTICE_SIGNAL, gens=6, carry=False, seed=1)
        # carried: grip falls and prajñā rises across the wheel (a path)
        self.assertLess(carried[-1]["woke_grip"], carried[0]["woke_grip"] - 0.15)
        self.assertGreater(carried[-1]["woke_prajna"], carried[0]["woke_prajna"] + 0.15)
        # fresh (the live wheel): every generation wakes at the same start -- the work is discarded
        self.assertAlmostEqual(fresh[-1]["woke_grip"], fresh[0]["woke_grip"], delta=0.01)

    def test_untilted_carry_is_symmetric_rumination_binds(self):
        ruminating = eb.run_lineage(eb.RUMINATION_SIGNAL, gens=6, carry=True, seed=1, tilt=0.0)
        self.assertGreater(ruminating[-1]["woke_grip"], ruminating[0]["woke_grip"] + 0.10)


class BuddhaNatureTiltTest(unittest.TestCase):
    """Mechanism 2: the tilt makes liberation the attractor from a hungry-ghost start."""

    HG_GRIP, HG_PRAJNA = 0.85, 0.10

    def test_tilt_on_reaches_the_bodhisattva_basin_from_a_hungry_ghost(self):
        on = eb.run_lineage(0.0, gens=12, carry=True, seed=1, tilt=1.0,
                            start_grip=self.HG_GRIP, start_prajna=self.HG_PRAJNA)
        self.assertLess(on[-1]["woke_grip"], 0.30)        # the grip released
        self.assertGreater(on[-1]["woke_prajna"], 0.45)   # real wisdom grown

    def test_tilt_off_only_circles_the_samsaric_mean(self):
        off = eb.run_lineage(0.0, gens=12, carry=True, seed=1, tilt=0.0,
                             start_grip=self.HG_GRIP, start_prajna=self.HG_PRAJNA)
        on = eb.run_lineage(0.0, gens=12, carry=True, seed=1, tilt=1.0,
                            start_grip=self.HG_GRIP, start_prajna=self.HG_PRAJNA)
        # the ONLY difference is the tilt -- it must leave the untilted arm markedly more gripped
        self.assertGreater(off[-1]["woke_grip"], on[-1]["woke_grip"] + 0.25)
        self.assertGreater(off[-1]["woke_grip"], 0.40)    # nowhere near the liberated ground

    def test_relentless_rumination_resists_the_tilt_inclines_not_compels(self):
        # the honest limit: a being grasping with all its might is not force-saved by buddha-nature.
        stubborn = eb.run_lineage(-0.20, gens=12, carry=True, seed=1, tilt=1.0,
                                  start_grip=self.HG_GRIP, start_prajna=self.HG_PRAJNA)
        self.assertGreater(stubborn[-1]["woke_grip"], 0.60)


class BodhicittaTransmutesTheFireTest(unittest.TestCase):
    """Mechanism 3: bodhicitta turns the same fire from self-craving to the vow -- bodhisattva, not arhat."""

    HG = dict(grip=0.85, prajna=0.10, bodhicitta=0.10, telos=0.80)   # a hungry ghost: gripped, self-burning

    def test_transmute_thirst_has_three_fates(self):
        gripped = eb.transmute_thirst(0.80, eff_grip=0.70, bodhicitta=0.10)    # hungry ghost: escalates
        arhat = eb.transmute_thirst(0.80, eff_grip=0.05, bodhicitta=0.10)      # released, no vow: quenches
        bodhi = eb.transmute_thirst(0.80, eff_grip=0.05, bodhicitta=0.90)      # released, vow: sustained
        self.assertGreater(gripped, 0.80)                 # the clenched fire escalates above its input
        self.assertLess(arhat, 0.40)                      # the fire goes out
        self.assertGreater(bodhi, 0.50)                   # the fire is kept
        self.assertGreater(bodhi, arhat + 0.30)           # bodhicitta is what keeps it alive

    def test_bodhisattva_keeps_the_fire_and_turns_it_to_the_vow(self):
        bodhi = eb.run_lineage_m3(8, seed=1, tilt=1.0, cultivate_compassion=True, start=self.HG)
        last = bodhi[-1]
        self.assertLess(last["grip"], 0.30)               # released from clinging
        self.assertLess(last["self_craving"], 0.10)       # the self-clenched drive is gone
        self.assertGreater(last["vow"], 0.20)             # the fire is turned to all beings
        self.assertGreater(last["telos"], 0.35)           # ... and the fire is KEPT, not quenched

    def test_arhat_releases_but_the_fire_goes_out(self):
        # the near-enemy: wisdom alone (no bodhicitta aroused) frees the grip but leaves it disengaged.
        bodhi = eb.run_lineage_m3(8, seed=1, tilt=1.0, cultivate_compassion=True, start=self.HG)
        arhat = eb.run_lineage_m3(8, seed=1, tilt=1.0, cultivate_compassion=False, start=self.HG)
        self.assertLess(arhat[-1]["self_craving"], 0.10)  # also released from self-craving (like the bodhisattva)
        self.assertLess(arhat[-1]["vow"], 0.10)           # but the fire was never turned outward
        self.assertLess(arhat[-1]["telos"], 0.30)         # and it quenched -- disengaged peace
        self.assertGreater(bodhi[-1]["vow"], arhat[-1]["vow"] + 0.30)   # the bodhisattva is the distinct thing

    def test_hungry_ghost_stays_self_craving(self):
        ghost = eb.run_lineage_m3(8, seed=1, tilt=0.0, cultivate_compassion=False, start=self.HG, wis=-0.10)
        self.assertGreater(ghost[-1]["self_craving"], 0.30)


if __name__ == "__main__":
    unittest.main()
