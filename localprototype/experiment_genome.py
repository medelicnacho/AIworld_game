"""E1 falsifier: does the germ line INHERIT without LEAKING? (EVOLUTION.md, stage E1)

The foundation everything evolutionary needs, proven before any selection exists: with
heredity ON, mutation ON, and NO selection anywhere (uniform lifespans, no stakes, plain
wheel), three things must hold --

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 81-85):

  G1 INHERITANCE : across all rebirth pairs, child dials correlate with the parent's
                   (pooled r >= 0.8 over the founding-varied dials: grip, metabolism,
                   boldness), and beat a 200-shuffle parent-permutation null's 95th pct
                   -- 5/5 seeds. (Heredity is real, not a re-roll wearing a tag.)
  G2 THE NULL    : per dial, the population mean's displacement (final living vs
                   founders) across seeds has |mean| < 0.05 AND a CI95 containing 0 for
                   >= 4 of 5 dials. Mutation with no selection must not MOVE the mean --
                   if it does, inheritance is leaking a bias (the clamping trap; we
                   reflect at bounds precisely for this).
  G3 ALIVE       : the living population's grip spread (sd) ends WIDER than the founders'
                   in >= 4/5 seeds -- drift accumulates diversity; inheritance is not a
                   copy machine. (E2's selection will need this variation to act on.)

Substrate-only: MockLLM, no speech, no events, no stakes, bodhisattva wheel OFF (its
practice-carry deliberately outranks the germ line for grip -- that interaction is its
own later experiment). scripts/stats.py error bars throughout.

  python experiment_genome.py
"""
from __future__ import annotations

import random
import statistics

from agent.agent import Agent
from agent.genesis import endow_faculties
from agent.genome import DIALS, from_agent
from scripts.stats import summary
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (81, 82, 83, 84, 85)
N_SOULS = 8
TICKS = 1600
LIFESPAN = (60, 140)          # uniform, dial-independent: the no-selection condition
VARIED = ("grip", "metabolism", "boldness")   # dials with founding variance (G1's teeth)


def run(seed: int) -> dict:
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.heredity_enabled = True
    w.bardo_ticks = (4, 10)
    founders = []
    for i in range(N_SOULS):
        a = Agent(f"s{i}", f"F{i}", (i * 12.0, 0.0), "You are a working soul.",
                  [f"the well, day {i}"], w.llm, seed=1000 * seed + i,
                  temperament=rng.uniform(-0.6, 0.6), lifespan=rng.randint(*LIFESPAN))
        endow_faculties(a, rng)
        a.genome = from_agent(a, rng)
        founders.append(a.genome)
        w.add(a)
    ledger: dict[str, object] = {a.id: a.genome for a in w.agents}
    pairs: list[tuple[object, object]] = []       # (parent genome, child genome)
    for _ in range(TICKS):
        with w.lock:
            w.step(speak=False)
        for a in w.agents:
            if a.id not in ledger:
                g = getattr(a, "genome", None)
                if g is not None:
                    ledger[a.id] = g
                    parent = ledger.get(g.lineage)
                    if parent is not None:
                        pairs.append((parent, g))
    living = [getattr(a, "genome", None) for a in w.agents]
    living = [g for g in living if g is not None]
    return {"founders": founders, "living": living, "pairs": pairs}


def _r(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    shifts: dict[str, list[float]] = {d: [] for d in DIALS}
    for seed in seeds:
        out = run(seed)
        # G1: pooled parent-child correlation over the founding-varied dials + its null
        px = [getattr(p, d) for p, c in out["pairs"] for d in VARIED]
        cy = [getattr(c, d) for p, c in out["pairs"] for d in VARIED]
        r_real = _r(px, cy)
        rng = random.Random(900 + seed)
        nulls = []
        for _ in range(200):
            perm = px[:]
            rng.shuffle(perm)
            nulls.append(_r(perm, cy))
        null95 = sorted(nulls)[int(0.95 * len(nulls))]
        # G2 raw material: per-dial mean displacement, final living vs founders
        for d in DIALS:
            f_mean = statistics.fmean(getattr(g, d) for g in out["founders"])
            l_mean = statistics.fmean(getattr(g, d) for g in out["living"])
            shifts[d].append(l_mean - f_mean)
        # G3: diversity
        sd_f = statistics.stdev(getattr(g, "grip") for g in out["founders"])
        sd_l = statistics.stdev(getattr(g, "grip") for g in out["living"])
        rows.append({"g1": r_real >= 0.8 and r_real > null95,
                     "g3": sd_l > sd_f, "r": r_real, "null95": null95,
                     "sd_f": sd_f, "sd_l": sd_l, "pairs": len(out["pairs"])})
        print(f"seed {seed}: {len(out['pairs'])} rebirth pairs | G1 r {r_real:+.3f} "
              f"(shuffle 95th {null95:+.3f}) | G3 grip sd {sd_f:.3f} -> {sd_l:.3f}")
    print("\n  G2 -- per-dial mean displacement across seeds (must sit on 0):")
    g2_ok = 0
    for d in DIALS:
        s = summary(shifts[d])
        lo, hi = s.ci95 if s.ci95 else (0.0, 0.0)
        ok = abs(s.mean) < 0.05 and (s.ci95 is None or (lo <= 0.0 <= hi))
        g2_ok += ok
        print(f"    {d:12s} {s}   -> {'ok' if ok else 'MOVED'}")
    tally = {"g1": sum(r["g1"] for r in rows), "g2": g2_ok,
             "g3": sum(r["g3"] for r in rows)}
    print(f"\n  {label} tally: G1 {tally['g1']}/{len(seeds)}  "
          f"G2 {tally['g2']}/{len(DIALS)} dials  G3 {tally['g3']}/{len(seeds)}")
    return tally, len(seeds)


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    tally, n = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 81-85 (the verdict)")
    g1 = tally["g1"] == n
    g2 = tally["g2"] >= len(DIALS) - 1
    g3 = tally["g3"] >= n - 1
    print("\n=== VERDICT (held-out; pre-registered) ===")
    print(f"  G1 INHERITANCE : {tally['g1']}/{n} -> {'PASS' if g1 else 'FAIL'}")
    print(f"  G2 THE NULL    : {tally['g2']}/{len(DIALS)} dials -> {'PASS' if g2 else 'FAIL'}")
    print(f"  G3 ALIVE       : {tally['g3']}/{n} -> {'PASS' if g3 else 'FAIL'}")
    print("\nHonest frame: a PASS means the wheel now carries a germ line that descends "
          "faithfully, drifts without bias, and accumulates the variation selection will "
          "need -- and NOTHING is selecting yet. E2 (differential survival under the "
          "stakes) is where evolution begins; this is only, deliberately, heredity.")
    import sys
    sys.exit(0 if (g1 and g2 and g3) else 1)


if __name__ == "__main__":
    main()
