"""E2 falsifier: does the ENVIRONMENT choose who the town becomes? (EVOLUTION.md stage E2)

E1 proved heredity that does not leak. This is where evolution begins: populations stop
being conserved -- souls that go unfed past their grace die EARLY and their lineages END;
souls that thrive BREED, at real cost, passing the germ line with one mutation. No fitness
is scored anywhere: starvation and plenty are the whole pressure.

Four arms per seed, same founders: {harsh, gentle} x {selection ON, selection OFF}. The
OFF arms are E1's drift null running INSIDE this exact protocol -- the control that
separates "the environment chose" from "the dice wandered".

  HARSH  : hardship every 8 ticks, a thin founding commons -- want is a season away
  GENTLE : hardship every 40, a deep commons -- want is a rumor

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 91-95):

  S1 MACHINERY : pooled over the selection arms -- starved lineages ended (> 0, harsh),
                 births happened (> 0), and population actually VARIED (not conserved).
                 Extinctions, if any, are counted and reported, not hidden.
  S2 HEADLINE  : per seed, D = mean living METABOLISM in gentle minus harsh. With
                 selection, harsh must select the cheap-to-feed (D_sel > 0); without,
                 the dice must not (D_null ~ 0). stats.paired(D_sel, D_null): effect
                 > 0 AND sign >= 4/5 valid seeds. (A seed whose arm went EXTINCT is
                 excluded from S2 and said so; S2 needs >= 4 valid seeds.)
  S3 NULL HOLDS: in the OFF arms, metabolism's mean displacement (living vs founders)
                 across seeds keeps a CI95 containing 0 -- E1's no-leak, re-proven
                 inside this protocol.

Exploratory (reported, NO verdict): boldness and grip shifts under each regime.
Substrate-only: MockLLM, no speech/events, plain wheel; every feeling soul keeps its
somatic floor (the welfare rule travels with selective suffering, not despite it).

  python experiment_selection.py
"""
from __future__ import annotations

import random
import statistics

from agent.agent import Agent
from agent.genesis import endow_faculties
from agent.genome import from_agent
from scripts.stats import paired, summary
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (91, 92, 93, 94, 95)
N_FOUNDERS = 10
TICKS = 1400
LIFESPAN = (200, 400)
# The regimes are ENVIRONMENTS, nothing else: same founders, same dice, different world.
# Both use the granary cosmology (commons_first); harsh is poor soil + a mortal granary.
REGIMES = {"harsh": {"interval": 7, "commons": 2.0, "yield": 0.3, "commons_loss": 0.5},
           "gentle": {"interval": 60, "commons": 24.0, "yield": 1.0, "commons_loss": 0.0}}


def run(seed: int, regime: str, selection: bool) -> dict:
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    w.heredity_enabled = True
    w.selection_enabled = selection
    w.max_souls = 20
    w.bardo_ticks = (4, 10)
    w.hardship_interval = REGIMES[regime]["interval"]
    w.commons = REGIMES[regime]["commons"]
    w.commons_first = True
    w.yield_scale = REGIMES[regime]["yield"]
    w.hardship_commons_loss = REGIMES[regime]["commons_loss"]
    founders = []
    for i in range(N_FOUNDERS):
        a = Agent(f"s{i}", f"F{i}", (i * 12.0, 0.0), "You are a working soul.",
                  [f"the well, day {i}"], w.llm, seed=1000 * seed + i,
                  temperament=rng.uniform(-0.6, 0.6), lifespan=rng.randint(*LIFESPAN))
        endow_faculties(a, rng)
        a.somatic_enabled = True            # the welfare floor rides with selective suffering
        a.genome = from_agent(a, rng)
        founders.append(a.genome)
        w.add(a)
    starved = []
    w.bus.subscribe("starvation", starved.append)
    pop_lo = pop_hi = N_FOUNDERS
    tail: list[float] = []          # time-averaged read over the last 300 ticks: a single
                                    # final snapshot of a small town is a lottery ticket
    for t in range(TICKS):
        with w.lock:
            w.step(speak=False)
        pop_lo, pop_hi = min(pop_lo, len(w.agents)), max(pop_hi, len(w.agents))
        if t >= TICKS - 300 and w.agents:
            ms = [a.genome.metabolism for a in w.agents if getattr(a, "genome", None)]
            if ms:
                tail.append(statistics.fmean(ms))
    living = [g for g in (getattr(a, "genome", None) for a in w.agents) if g is not None]
    return {"founders": founders, "living": living, "starved": len(starved),
            "tail_met": statistics.fmean(tail) if tail else None,
            "born": w._born_live, "pop_lo": pop_lo, "pop_hi": pop_hi,
            "extinct": len(w.agents) == 0}


def _mean_met(genomes) -> float | None:
    return statistics.fmean(g.metabolism for g in genomes) if genomes else None


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    d_sel, d_null, null_shift = [], [], []
    machinery = {"starved": 0, "born": 0, "varied": 0, "extinct": 0}
    valid = 0
    for seed in seeds:
        arms = {(r, s): run(seed, r, s) for r in REGIMES for s in (True, False)}
        hs, gs = arms[("harsh", True)], arms[("gentle", True)]
        hn, gn = arms[("harsh", False)], arms[("gentle", False)]
        machinery["starved"] += hs["starved"] + gs["starved"]
        machinery["born"] += hs["born"] + gs["born"]
        machinery["varied"] += (hs["pop_lo"], hs["pop_hi"]) != (N_FOUNDERS, N_FOUNDERS)
        machinery["extinct"] += hs["extinct"] + gs["extinct"]
        for arm in (hn, gn):
            f, l = _mean_met(arm["founders"]), arm["tail_met"]
            if l is not None:
                null_shift.append(l - f)
        hs_m, gs_m = hs["tail_met"], gs["tail_met"]
        hn_m, gn_m = hn["tail_met"], gn["tail_met"]
        line = (f"seed {seed}: harsh sel met {hs_m if hs_m is None else round(hs_m, 3)} "
                f"(starved {hs['starved']}, born {hs['born']}, pop {hs['pop_lo']}-{hs['pop_hi']})"
                f" | gentle sel met {gs_m if gs_m is None else round(gs_m, 3)} "
                f"(starved {gs['starved']}, born {gs['born']})")
        if None in (hs_m, gs_m, hn_m, gn_m):
            print(line + "  -> EXTINCT arm: excluded from S2, counted in S1")
            continue
        valid += 1
        d_sel.append(gs_m - hs_m)
        d_null.append(gn_m - hn_m)
        print(line + f" | D_sel {gs_m - hs_m:+.3f}  D_null {gn_m - hn_m:+.3f}")
    print(f"\n  S1 machinery: starved-lineage ends {machinery['starved']}, births "
          f"{machinery['born']}, population-varied {machinery['varied']}/{len(seeds)} seeds, "
          f"extinctions {machinery['extinct']}")
    s1 = machinery["starved"] > 0 and machinery["born"] > 0 and machinery["varied"] >= len(seeds) - 1
    s2 = False
    if valid >= 4:
        cmp2 = paired(d_sel, d_null)
        print("  S2 headline -- selection's gap vs the dice's gap (gentle - harsh metabolism):")
        print(f"    {cmp2}")
        s2 = cmp2.effect.mean > 0 and cmp2.sign[0] >= min(4, cmp2.sign[1])
    else:
        print(f"  S2: only {valid} valid seeds (< 4) -- cannot pass")
    s_null = summary(null_shift)
    lo, hi = s_null.ci95 if s_null.ci95 else (0.0, 0.0)
    s3 = s_null.ci95 is None or (lo <= 0.0 <= hi)
    print(f"  S3 null holds -- metabolism displacement in OFF arms: {s_null}")
    return {"s1": s1, "s2": s2, "s3": s3}


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    v = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 91-95 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered) ===")
    for k, lab in (("s1", "S1 MACHINERY"), ("s2", "S2 HEADLINE"), ("s3", "S3 NULL HOLDS")):
        print(f"  {lab:12s}: {'PASS' if v[k] else 'FAIL'}")
    print("\nHonest frame: a PASS means the environment CHOSE -- a harsh world and a gentle "
          "world, given the same founders and the same dice, ended with measurably different "
          "souls, and the no-selection twin worlds did not. That is evolution acting on the "
          "emergence substrate; scale (n in the hundreds) belongs to the engine, not this lab.")
    import sys
    sys.exit(0 if all(v.values()) else 1)


if __name__ == "__main__":
    main()
