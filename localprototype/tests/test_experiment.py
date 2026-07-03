"""Tests for the experiment harness: replicates must be reproducible and the
treatment-vs-control comparison must detect a real perturbation.

These assert the three properties that make this an experiment rather than a
demo: (1) a (seed, events) replicate is deterministic -- rerun it, get the same
number; (2) toggling events changes the metric; (3) a paired comparison over a
strong negative event reports a negative effect with the right shape.

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_experiment.py
"""

from __future__ import annotations

import unittest

# allow `python tests/test_experiment.py` from anywhere

import experiment
from agent.agent import Agent
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

# A self-contained scenario: two flat-temperament agents and one strong
# negative event, so the expected direction of the effect is unambiguous.
_EVENT = WorldEvent("collapse", "everything is falling apart around us",
                    tick=5, emotion=-0.9, urge=0.6)


def _build(seed: int, events_enabled: bool) -> World:
    llm = MockLLM(seed=seed)
    world = World(events=[_EVENT], events_enabled=events_enabled)
    for i, aid in enumerate(("a0", "a1")):
        world.add(Agent(aid, aid.upper(), (0.0, 0.0), "a persona",
                        ["a seed phrase"], llm, seed=seed + i + 1, temperament=0.0))
    return world


def _run(seed, events_enabled, ticks=20):
    return experiment.run_replicate(seed, events_enabled, ticks, build=_build)


class ExperimentTest(unittest.TestCase):
    def test_a_replicate_is_deterministic(self):
        self.assertEqual(_run(42, True), _run(42, True),
                         "same (seed, events) must reproduce the exact metric")
        self.assertEqual(_run(42, False), _run(42, False))

    def test_toggling_events_changes_the_metric(self):
        self.assertNotEqual(_run(42, True), _run(42, False),
                            "the event must move the behavioral metric")

    def test_paired_comparison_detects_a_negative_event(self):
        seeds = list(range(100, 108))
        r = experiment.compare(seeds, ticks=20, build=_build)

        self.assertEqual(len(r["diffs"]), len(seeds))
        self.assertEqual(len(r["treatment"]), len(seeds))
        self.assertLess(r["effect_mean"], 0.0,
                        "a strong negative event must lower mean mood")
        self.assertLess(r["treatment_mean"], r["control_mean"])
        self.assertGreaterEqual(r["effect_std"], 0.0)

    def test_stats_helpers_on_known_input(self):
        # constant positive differences: zero spread -> infinite t, d
        self.assertEqual(experiment.cohens_d_paired([0.5, 0.5, 0.5]), float("inf"))
        self.assertEqual(experiment.paired_t([0.5, 0.5, 0.5]), float("inf"))
        # symmetric around zero -> zero effect
        self.assertAlmostEqual(experiment.paired_t([-1.0, 1.0]), 0.0)
        # too few points -> defined, not a crash
        self.assertEqual(experiment.cohens_d_paired([0.5]), 0.0)


if __name__ == "__main__":
    unittest.main()
