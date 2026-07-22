"""The frozen trajectories, and the isolation the Worker model assumes.

Both exist for gameworld's M2. A keystone that passes or fails at the END of a run says
THAT the port is wrong; a frozen trajectory says WHERE. And a Worker per settlement is only
safe if N Worlds genuinely share nothing -- `services/embed` holds module-level caches and
`_FORCE_JACCARD` is a global, so it was worth checking rather than assuming.
"""

from scripts.arena_harness import build, run
from scripts.golden import check


def test_the_lab_still_reproduces_its_own_frozen_trajectories():
    """The oracle test. A failure here is a BEHAVIOUR CHANGE -- read the diff before
    regenerating: scripts/golden.py --write is not a way to make this pass."""
    bad = check()
    assert not bad, bad[:6]


def _fingerprint(w):
    return (len(w.agents),
            round(sum(a.position[0] for a in w.agents), 9),
            round(sum(a.position[1] for a in w.agents), 9),
            round(sum(a.wellbeing for a in w.agents), 9),
            sum(len(a.memory.items) for a in w.agents))


def test_worlds_are_isolated_from_each_other():
    """Three worlds stepped INTERLEAVED must equal the same three stepped ALONE. If any
    module-level state leaked between them, a Worker-per-settlement port would produce
    different towns than the lab and no keystone would explain why."""
    ticks = 200
    alone = [_fingerprint(run(build(seed=sd, founders=10), ticks)) for sd in (11, 12)]
    ws = [build(seed=sd, founders=10) for sd in (11, 12)]
    for t in range(1, ticks + 1):
        for w in ws:
            w.step(speak=False)
            if t % 7 == 0:
                w.speak_turn()
    assert alone == [_fingerprint(w) for w in ws]


def test_a_world_does_not_disturb_a_second_built_after_it():
    """Construction order must not matter either -- a shard spun up mid-session has to
    behave like one spun up at boot."""
    ticks = 150
    solo = _fingerprint(run(build(seed=13, founders=10), ticks))
    _ = run(build(seed=99, founders=10), 50)          # a noisy neighbour, first
    later = _fingerprint(run(build(seed=13, founders=10), ticks))
    assert solo == later
