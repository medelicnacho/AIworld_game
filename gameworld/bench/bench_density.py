"""Is the superlinear cost POPULATION or LOCAL DENSITY?

If it is density, an open world fixes it for free: chunked settlements of ~30 souls
spread over a big map stay cheap no matter how large the world gets. If it is raw
population, you need hard LOD tiers.

Same n, three worlds: tight (dense), spread (sparse), and murmur off.
Plus a 'lived-in' run with real speech turns so memory + bonds are populated.
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

embed.use_jaccard_only(True)


def build(n: int, span: float, murmur: bool, seed: int = 7) -> World:
    w = World(move_enabled=True, move_seed=seed, murmur_enabled=murmur,
              bounds=(span, span))
    w.llm = MockLLM(seed=seed)
    s = 12345
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        x = (s % int(span))
        s = (s * 1103515245 + 12345) % 2147483648
        y = (s % int(span))
        a = Agent(f"s{i}", f"Soul{i}", (float(x), float(y)), "You are a working soul.",
                  [f"the well, the field, the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0, lifespan=100000)
        a.bond_enabled = True
        w.add(a)
    return w


def bench(w, ticks: int, speak: bool = False) -> dict:
    for _ in range(20):
        w.advance()
        w.animate()
    t0 = time.perf_counter()
    for _ in range(ticks):
        w.advance()
        w.animate()
        if speak:
            w.speak_turn()
    dt = (time.perf_counter() - t0) / ticks
    mem = sum(len(a.memory.items) for a in w.agents)
    bonds = sum(len(getattr(a, "bonds", {})) for a in w.agents)
    return {"ms": dt * 1000, "mem": mem, "bonds": bonds}


N = 256
print(f"n={N}, 120 ticks each\n")
print(f"{'world':<34} {'tick ms':>9} {'mem items':>10} {'bonds':>7}")
for label, span, murmur in (
        ("dense   (span 500, murmur on)", 500.0, True),
        ("medium  (span 2000, murmur on)", 2000.0, True),
        ("spread  (span 8000, murmur on)", 8000.0, True),
        ("dense   (span 500, murmur OFF)", 500.0, False),
        ("spread  (span 8000, murmur OFF)", 8000.0, False)):
    r = bench(build(N, span, murmur), 120)
    print(f"{label:<34} {r['ms']:>9.2f} {r['mem']:>10} {r['bonds']:>7}")

print("\n-- lived-in: mock speech turns running (bonds + memory populate) --")
for label, span in (("dense  (span 500)", 500.0), ("spread (span 8000)", 8000.0)):
    r = bench(build(N, span, True), 300, speak=True)
    print(f"{label:<34} {r['ms']:>9.2f} {r['mem']:>10} {r['bonds']:>7}")
