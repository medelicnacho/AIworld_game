"""Does the emergence recipe survive in the REAL voice? -- validate the CulturePool port (§5.13).

The abstract model (experiment_memetic.py) used fixed whole-phrase memes. The live voice recombines, so
this drives the ACTUAL MarkovLLM(culture=True) in the real feedback loop -- she speaks a recombination, it
enters memory, the culture re-weights, she speaks again -- and checks the §5.13 result transfers:

  CONCENTRATES : a reigning MOTIF emerges (its weight is a real share, not uniform).
  LIVES        : the reigning motif TURNS OVER (eras), not frozen, not per-step noise.
  EMERGENT     : different seeds settle into different eras (path-dependent).

  python experiment_culture_live.py
"""
from __future__ import annotations

import collections
import random
import statistics

from experiment_memetic import MEMES as TOWN
from services.llm import MarkovLLM


def run(seed: int, steps: int = 260, burn: int = 60):
    llm = MarkovLLM(seed=seed, culture=True)
    rng = random.Random(seed)
    mem = collections.deque(TOWN, maxlen=140)
    reigns = []
    for _ in range(steps):
        llm.learn(list(mem))
        mem.append(llm.generate(""))          # she speaks a recombination -> memory
        # the town keeps talking, and it SHARES the culture -- it preferentially repeats the reigning
        # motifs (real feedback), not a uniform-random source (which would fight concentration)
        wts = [1.0 + 6.0 * llm.culture.weight_of(p) for p in TOWN]
        mem.append(rng.choices(TOWN, weights=wts, k=1)[0])
        reigns.append(llm.culture.reigning())
    post = [r for r in reigns[burn:] if r]
    turnover = sum(1 for i in range(1, len(post)) if post[i] != post[i - 1])
    tot = sum(llm.culture.mw.values()) or 1.0
    share = (max(llm.culture.mw.values()) / tot) if llm.culture.mw else 0.0
    return {"turnover": turnover, "steps": len(post), "distinct": len(set(post)),
            "share": share, "era": llm.culture.era(3), "seq": post}


def _eras(seq, min_run=3):
    """Collapse the reign sequence into (motif, length) eras, dropping flickers shorter than min_run."""
    out = []
    for r in seq:
        if out and out[-1][0] == r:
            out[-1][1] += 1
        else:
            out.append([r, 1])
    return [(m, n) for m, n in out if n >= min_run]


def _overlap(sets):
    pairs = [(a, b) for i, a in enumerate(sets) for b in sets[i + 1:]]
    return statistics.mean(len(a & b) / len(a | b) for a, b in pairs) if pairs else 1.0


def main() -> None:
    seeds = range(6)
    print("=" * 82)
    print("LIVE CULTURE: does the emergence recipe survive in the real recombining voice?")
    print("  real MarkovLLM(culture=True) in the speak->observe feedback loop; 6 seeds")
    print("=" * 82)
    res = [run(s) for s in seeds]
    print(f"{'seed':>4} | {'top-motif share':>15} | {'turnovers':>9} | {'distinct reigns':>15} | reigning era")
    print("-" * 82)
    for s, r in zip(seeds, res):
        print(f"{s:>4} | {r['share']:>15.3f} | {r['turnover']:>9} | {r['distinct']:>15} | "
              f"\"{r['era'][0]}\"")
    print("-" * 82)

    share = statistics.mean(r["share"] for r in res)
    turn = statistics.mean(r["turnover"] for r in res)
    steps = res[0]["steps"]
    overlap = _overlap([set(r["era"]) for r in res])
    concentrates = share > 0.04                          # a real reigning motif (uniform would be ~1/#motifs)
    lives = 3 < turn < 0.8 * steps                       # turns over, but not per-step noise
    emergent = overlap < 0.5
    print("CONCENTRATES (a motif reigns) :", "YES ✓" if concentrates else "NO ✗",
          f"(mean top-motif share {share:.3f})")
    print("LIVES (eras turn over)        :", "YES ✓" if lives else "NO ✗",
          f"(mean {turn:.0f} turnovers over {steps} steps -- not frozen, not noise)")
    print("EMERGENT (path-dependent)     :", "YES ✓" if emergent else "NO ✗",
          f"(cross-seed reigning-era overlap {overlap:.2f})")
    print()
    print("  Seed 0's cultural eras (motif × how long it reigned):")
    for m, n in _eras(res[0]["seq"])[:10]:
        print(f"    {n:>3} readings:  \"{m}\"")
    print("=" * 82)


if __name__ == "__main__":
    main()
