"""scripts/arena_harness.py -- the one correct way to build and run a headless arena.

Written after two arena verdicts were voided by faults that were BOTH in the harness and
NEITHER in the substrate. An experiment that builds its own world by hand repeats them:

  1. NONDETERMINISM. World defaults `move_seed=None` -> `random.Random(None)` -> the
     movement RNG is seeded from OS ENTROPY. A world built as
     `World(rebirth_enabled=False, events_enabled=False)` is a DIFFERENT world every run:
     measured, three identical calls gave 60 / 56 / 46 souls alive, and two same-seed
     worlds diverge at TICK 1. Every on-vs-off row in such an experiment compares two
     different worlds and its pass counts are partly run-to-run noise.

  2. NO OPINION DYNAMICS. `w.step(speak=False)` makes ZERO hear() calls -- measured: 300
     ticks, 0 hear(), 0 _bounded_confidence(). The live arena speaks from a SEPARATE
     speak_turn() thread (santana_app/evolution.py run_speech, ~every 0.6s against the
     wheel's 0.08s), which nothing headless calls unless it is told to. Beliefs then move
     only by inheritance-at-birth: they never assimilate, repel, or individuate. Any
     mechanism that reads belief is being tested against a landscape that cannot change.

So: build with `build()`, run with `run()`, and assert `self_check()` in the test suite.
Both faults are structurally impossible through this door.

    from scripts.arena_harness import build, run
    w = build(seed=11, founders=24)          # deterministic, speaking
    run(w, ticks=2000)
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The live arena's own cadence: run_wheel sleeps 0.08s per tick, run_speech 0.6s per turn.
# One speech turn per ~7 ticks reproduces that ratio deterministically, without threads.
SPEAK_EVERY = 7


def build(seed: int, founders: int = 24, regime: str = "watch", speak: bool = True):
    """A deterministic arena world, founded and gated exactly as the live one is.

    `move_seed` is the load-bearing argument -- without it the movement RNG comes from OS
    entropy and nothing downstream is reproducible. `speak=False` is available for a
    deliberate no-speech control, but it is NOT the arena: say so in any verdict that uses it.
    """
    from santana_app.evolution import _found_settlements, _gates
    from services import embed as _embed
    from services.llm import MockLLM
    from world.sim import World
    # Lexical similarity, as the arena itself runs it: santana_app/run.py forces
    # use_jaccard_only(True) for any town past the founder threshold ("big towns run the
    # lexical similarity everywhere: identical mechanics, no per-pair embedding cost, no
    # network in the wheel"). Not a shortcut -- matching it is what makes a headless run a
    # read of the ARENA rather than of some faster-but-different world.
    #
    # It is also the difference between a usable harness and an unusable one. With an
    # Ollama instance up, every hear() reaches for a real embedding over HTTP: measured,
    # 300 ticks took 133s wall against 5.6s of CPU -- ~96% of it blocked on localhost.
    # Forced to Jaccard the same run takes 1.5s. An experiment nobody can afford to run
    # enough times is an experiment that ships underpowered.
    _embed.use_jaccard_only(True)
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=seed)
    w.llm = MockLLM(seed=seed)
    _gates(w, founders, regime=regime)
    _found_settlements(w, random.Random(seed), founders)
    w._harness_speak = speak
    return w


def run(w, ticks: int, speak_every: int = SPEAK_EVERY, on_sample=None, every: int = 0):
    """Step the world AND take speech turns, the way the live arena actually runs.

    on_sample(tick, world) is called every `every` ticks (0 = never) -- for trajectory
    probes, so they do not each reinvent a sampling loop with its own bugs."""
    speaking = getattr(w, "_harness_speak", True)
    for t in range(1, ticks + 1):
        w.step(speak=False)
        if speaking and speak_every > 0 and t % speak_every == 0:
            w.speak_turn()
        if every and on_sample and t % every == 0:
            on_sample(t, w)
    return w


# --- the harness's own falsifier ---------------------------------------------------------
def self_check(ticks: int = 120, seed: int = 11, founders: int = 12) -> dict:
    """Prove the two faults are gone: identical seeds give identical worlds, and souls
    actually hear each other. Returns the evidence rather than asserting, so a test can
    report WHICH half failed."""
    from agent.agent import Agent
    hits = {"hear": 0, "bounded_confidence": 0}
    orig_hear, orig_bc = Agent.hear, Agent._bounded_confidence

    def counted_hear(self, u, now, speaker_name=None):
        hits["hear"] += 1
        return orig_hear(self, u, now, speaker_name)

    def counted_bc(self, mine, other, spk):
        hits["bounded_confidence"] += 1
        return orig_bc(self, mine, other, spk)

    Agent.hear, Agent._bounded_confidence = counted_hear, counted_bc
    try:
        def fingerprint():
            w = run(build(seed=seed, founders=founders), ticks)
            return (len(w.agents),
                    round(sum(a.position[0] for a in w.agents), 6),
                    round(sum(a.position[1] for a in w.agents), 6))
        a, b = fingerprint(), fingerprint()
    finally:
        Agent.hear, Agent._bounded_confidence = orig_hear, orig_bc
    return {"deterministic": a == b, "run_a": a, "run_b": b,
            "hear": hits["hear"], "bounded_confidence": hits["bounded_confidence"]}


if __name__ == "__main__":
    r = self_check()
    print(f"  deterministic       : {'YES' if r['deterministic'] else 'NO'}   "
          f"{r['run_a']} vs {r['run_b']}")
    print(f"  hear() calls        : {r['hear']}")
    print(f"  opinion updates     : {r['bounded_confidence']}")
    ok = r["deterministic"] and r["hear"] > 0 and r["bounded_confidence"] > 0
    print(f"\n  HARNESS {'SOUND' if ok else 'STILL BROKEN'}")
