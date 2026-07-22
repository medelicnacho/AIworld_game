"""Capacity meter for an open-world port: how many souls can one CPU thread carry?

Measures advance() (the mind clock: memory decay/mutate, thought churn, urges, stakes)
and animate() (the body clock: social-force movement) SEPARATELY, because a game LODs
them differently -- distant souls can keep thinking at 1Hz while only nearby ones move
at frame rate.

Mock LLM, no speech turns (speech is tiered separately). Single thread, headless.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "localprototype"))

from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World

embed.use_jaccard_only(True)   # no embedding model; the substrate-only path a game ships


def build(n: int, seed: int = 7, move: bool = True) -> World:
    w = World(move_enabled=move, move_seed=seed, murmur_enabled=True, bounds=(4000.0, 4000.0))
    w.llm = MockLLM(seed=seed)
    rng_x = 0
    for i in range(n):
        rng_x = (rng_x * 1103515245 + 12345) % 2147483648
        x = (rng_x % 4000) / 1.0
        rng_x = (rng_x * 1103515245 + 12345) % 2147483648
        y = (rng_x % 4000) / 1.0
        a = Agent(f"s{i}", f"Soul{i}", (x, y), "You are a working soul.",
                  [f"the well, the field, the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0, lifespan=100000)
        a.bond_enabled = True
        w.add(a)
    return w


def bench(n: int, ticks: int = 120) -> dict:
    w = build(n)
    for _ in range(20):          # warm: let memory/bonds populate
        w.advance()
        w.animate()
    t0 = time.perf_counter()
    for _ in range(ticks):
        w.advance()
    t_mind = (time.perf_counter() - t0) / ticks
    t0 = time.perf_counter()
    for _ in range(ticks):
        w.animate()
    t_body = (time.perf_counter() - t0) / ticks
    bonds = sum(len(getattr(a, "bonds", {})) for a in w.agents)
    return {"n": n, "mind_ms": t_mind * 1000, "body_ms": t_body * 1000,
            "total_ms": (t_mind + t_body) * 1000,
            "tps": 1.0 / (t_mind + t_body), "bonds": bonds}


print(f"{'n':>6} {'mind ms':>9} {'body ms':>9} {'tick ms':>9} {'ticks/s':>9} "
      f"{'10Hz core%':>11} {'bonds':>8}")
for n in (16, 64, 128, 256, 512, 1024):
    r = bench(n, ticks=60 if n >= 512 else 120)
    print(f"{r['n']:>6} {r['mind_ms']:>9.2f} {r['body_ms']:>9.2f} {r['total_ms']:>9.2f} "
          f"{r['tps']:>9.0f} {r['total_ms'] * 10 / 10:>10.1f}% {r['bonds']:>8}")
