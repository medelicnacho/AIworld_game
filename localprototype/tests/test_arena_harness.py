"""Tests for the arena harness (scripts/arena_harness.py).

These exist because two arena verdicts were voided by faults that were both in the
harness and neither in the substrate: worlds built without move_seed were seeded from
OS entropy (three identical calls gave 60/56/46 souls alive), and step(speak=False)
made ZERO hear() calls, so no mechanism that reads belief was ever tested against a
living opinion landscape. These are the two assertions that would have caught both on
day one.
"""

from scripts.arena_harness import build, run, self_check


def test_the_harness_self_check_passes():
    """The falsifier, run as a test: same seed twice must give the SAME world, and
    souls must actually hear each other and move their opinions."""
    r = self_check(ticks=90, founders=10)
    assert r["deterministic"], (r["run_a"], r["run_b"])
    assert r["hear"] > 0, "no hear() calls -- the town is not speaking"
    assert r["bounded_confidence"] > 0, "no opinion updates -- beliefs cannot move"


def test_two_worlds_from_one_seed_are_identical():
    """move_seed is load-bearing: without it World seeds its movement RNG from OS
    entropy and two same-seed worlds diverge at TICK 1."""
    def fp(seed):
        w = run(build(seed=seed, founders=10), 60)
        return len(w.agents), round(sum(a.position[0] for a in w.agents), 6)
    assert fp(7) == fp(7)


def test_different_seeds_give_different_worlds():
    """The other direction -- a harness that is deterministic by being CONSTANT would
    pass the test above and measure nothing."""
    def fp(seed):
        w = run(build(seed=seed, founders=10), 60)
        return round(sum(a.position[0] for a in w.agents), 6)
    assert fp(7) != fp(8)


def test_speech_is_what_makes_beliefs_move():
    """The control that names the second fault: with speech off, the opinion dynamics
    do not run at all. This is why step(speak=False) alone is NOT the arena."""
    from agent.agent import Agent
    calls = {"n": 0}
    orig = Agent._bounded_confidence

    def counted(self, mine, other, spk):
        calls["n"] += 1
        return orig(self, mine, other, spk)

    Agent._bounded_confidence = counted
    try:
        calls["n"] = 0
        run(build(seed=11, founders=10, speak=False), 90)
        silent = calls["n"]
        calls["n"] = 0
        run(build(seed=11, founders=10, speak=True), 90)
        speaking = calls["n"]
    finally:
        Agent._bounded_confidence = orig
    assert silent == 0
    assert speaking > 0


def test_regime_passes_through_to_the_gates():
    from santana_app.evolution import REGIMES
    for regime in ("watch", "press"):
        w = build(seed=3, founders=8, regime=regime)
        assert w.yield_scale == REGIMES[regime]["yield_scale"]
        assert w.hardship_interval == REGIMES[regime]["hardship_interval"]


def test_sampling_hook_fires_on_schedule():
    seen = []
    run(build(seed=5, founders=8), 40, on_sample=lambda t, w: seen.append(t), every=10)
    assert seen == [10, 20, 30, 40]
