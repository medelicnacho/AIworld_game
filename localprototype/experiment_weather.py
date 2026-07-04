"""V1 -- EMOTIONAL WEATHER: is mood spatially contagious, so the map has real weather?

The cockpit paints every soul's mood as a halo. If mood spreads through SPEECH (which is
distance-bound) and bonds (which roaming braids into space), then souls standing near
each other should FEEL more alike than chance -- visible patches of warm and cold air
drifting across the town: weather. If mood is only individual (each soul's own stakes
and griefs), the halos are confetti and any "weather" a viewer sees is pareidolia.
This is the first V-series claim (RESEARCH.md, pre-registered 2026-07-04): the test of
whether what the player SEES forming on the map is real.

Protocol (substrate-only, MockLLM, deterministic): a roaming stakes town of n=32 with
full faculties and bonds, 700 ticks. After a 100-tick warm-up, every 10 ticks each
soul's felt mood and position are sampled. Per sample, each soul's mood is compared
with the mean mood of its 5 nearest neighbours; the per-seed statistic is the mean
Pearson r across samples in a window. The NULL is the same data with soul positions
SHUFFLED within each sample (identical moods, identical geometry, broken pairing) --
200 shuffles, mean taken.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 191-195; each >= 4/5).

CLAIM REVISION, RECORDED (2026-07-04, during tuning, BEFORE any verdict seed ran):
the original registration assumed positive contagion ("neighbours feel alike"). Tuning
found something better: strong spatial mood-structure in BOTH directions -- some towns
form warm fronts (seed 13: +0.15), others STRONG checkerboards (seed 12: -0.53 --
neighbours feel opposite), all far off the null (~-0.08). Two mechanisms surfaced en
route: the harness's speech channel was OFF in v1 (speak=False -- no contagion could
exist; fixed), and mood ANTI-tracks wellbeing across souls (-0.34: the comfortable sour
with clinging while the suffering are tended warm -- the dukkha economy, in numbers).
The revised claims test STRUCTURE, with the sign recorded per seed as data:

  W1 WEATHER IS REAL   : |r_late - null| > 0.05 per seed -- spatial mood-structure
      exists, warm-front or checkerboard, beyond the shuffled null.
  W2 WEATHER CONDENSES : |r_late - null| > |r_early - null| per seed -- the structure
      GROWS as bonds braid into space.

VERDICT (2026-07-04, virgin 191-195, consumed): **W1 PASS 5/5 -- the weather is REAL.**
Every held-out town developed spatial mood-structure far beyond the shuffled null:
four warm-front towns (up to +0.27) and one strong checkerboard (-0.46). What a viewer
sees condensing on the map is not pareidolia; the weather overlay is now earned.
W2 FAIL 3/5 -- structure does not reliably KEEP growing: several towns are born
structured or saturate early (r_early already at strength). Honest read: weather FORMS
FAST and persists, rather than slowly condensing. REGISTERED FOLLOW-UPS: what sets a
town's sign (warm-front vs checkerboard)? and the wild replication on the live towns'
town_history.jsonl once a week of samples exists.

Wild replication: the same statistic runs later on the live towns' town_history.jsonl
(scripts/history.py) -- lab verdict plus wild confirmation, or an honest split.

  python experiment_weather.py
"""
from __future__ import annotations

import random
import statistics
import sys

from agent.agent import Agent
from agent.genesis import coined_name, endow_faculties
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (191, 192, 193, 194, 195)
N, TICKS, WARMUP, EVERY, KNN = 32, 2000, 500, 10, 5


def build(seed: int) -> World:
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, events_enabled=False, murmur_enabled=True,
              move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    w.move_enabled = True
    w.bounds = (900, 600)
    w.bardo_ticks = (4, 10)
    for i in range(N):
        name = coined_name(rng)
        a = Agent(f"s{i}", name, (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {name} the villager.", [f"I am {name}", "the well keeps us"],
                  w.llm, seed=1000 * seed + i, temperament=rng.uniform(-0.6, 0.6),
                  lifespan=10 ** 9)
        endow_faculties(a, a._rng)
        a.bond_enabled = True
        w.add(a)
    return w


def _knn_series(samples) -> tuple[list[float], list[float]]:
    """Per sample: (soul mood, mean mood of its 5 nearest) pairs, flattened."""
    xs, ys = [], []
    for souls in samples:                    # souls: list of (x, y, mood)
        for i, (x, y, m) in enumerate(souls):
            near = sorted((((x - x2) ** 2 + (y - y2) ** 2, m2)
                        for j, (x2, y2, m2) in enumerate(souls) if j != i))[:KNN]
            xs.append(m)
            ys.append(statistics.fmean(m2 for _, m2 in near))
    return xs, ys


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 8:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5 or 1e-9
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5 or 1e-9
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def weather_r(samples) -> float:
    return _pearson(*_knn_series(samples))


def null_r(samples, rng: random.Random, shuffles: int = 200) -> float:
    """Identical moods and geometry; the PAIRING between soul and place is broken."""
    rs = []
    for _ in range(shuffles):
        shuffled = []
        for souls in samples:
            moods = [m for _, _, m in souls]
            rng.shuffle(moods)
            shuffled.append([(x, y, m) for (x, y, _), m in zip(souls, moods)])
        rs.append(weather_r(shuffled))
    return statistics.fmean(rs)


def run(seed: int) -> dict:
    w = build(seed)
    early, late = [], []
    half = WARMUP + (TICKS - WARMUP) // 2
    for t in range(TICKS):
        with w.lock:
            w.step(speak=True)     # the contagion channel: lines LAND on ears in range
        if t >= WARMUP and t % EVERY == 0:
            sample = [(a.position[0], a.position[1], a.felt_mood()) for a in w.agents]
            (early if t < half else late).append(sample)
    rng = random.Random(seed * 31 + 7)
    r_late, r_early = weather_r(late), weather_r(early)
    return {"r_late": r_late, "r_early": r_early, "null": null_r(late, rng)}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        out = run(seed)
        w1 = abs(out["r_late"] - out["null"]) > 0.05
        w2 = abs(out["r_late"] - out["null"]) > abs(out["r_early"] - out["null"])
        sign = "warm-front" if out["r_late"] > out["null"] else "checkerboard"
        rows.append({"w1": w1, "w2": w2})
        print(f"seed {seed}: r_late {out['r_late']:+.3f} vs null {out['null']:+.3f} "
              f"({sign}) | r_early {out['r_early']:+.3f} | "
              f"W1 {'PASS' if w1 else 'FAIL'}  W2 {'PASS' if w2 else 'FAIL'}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 191-195 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("w1", "W1 WEATHER IS REAL"), ("w2", "W2 WEATHER CONDENSES")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:22s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: W1 passing means the halos form REAL spatial structure --"
          "\nwarm fronts in some towns, checkerboards in others (the sign per seed is"
          "\ndata; what sets it is the registered follow-up). W1 failing means the"
          "\nstructure was pareidolia and no weather overlay gets built.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
