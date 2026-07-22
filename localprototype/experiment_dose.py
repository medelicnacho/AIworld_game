"""E2's DOSE-RESPONSE: does the environment select the traits, and does it beat drift?

EVOLUTION_NEXT stage 3. E2's own status says the mechanism is proven but the phenomenon is
"DIRECTIONAL-ONLY AT LAB SCALE": S2 passed at sign 4/5, d ~ +0.45, with a held-out CI that
included 0, and the M3 power rule (scripts/stats.py) says d ~ 0.45 needs ~40 seeds where
five have ~15% power. That verdict was explicitly deferred to "engine-scale n".

Two things make it affordable now. The arena has a `press` regime (lean graded land, where
E2's differential has room to appear) beside the shipped `watch` one, and the harness runs
a 2000-tick arm in ~40s -- so the full 40-seed target is ~110 minutes rather than a week.

Built on scripts/arena_harness (move_seed wired, speech running) after both earlier arena
verdicts were voided for lacking exactly those two things, and read with
scripts/arena_stats.genome_stats so the population read is the same one the live arenas use.

PRE-REGISTERED, on virgin seeds (tuning band 11-15 is NOT used for the verdict):

  D1 THE LAND SELECTS. Under selection, `press` (lean) ends with a LOWER population-mean
     metabolism than `watch` (kind) -- cheap-to-feed survives lean graded land. Paired per
     seed; reported with CI and an exact sign test.

  D2 IT BEATS DRIFT. Each regime's selected arm differs from its OWN no-selection twin by
     more than the twins differ from each other. Without this, D1 could be pure drift that
     happens to correlate with the regime.

  D3 VARIANCE SURVIVES. Trait sd does not collapse toward zero under selection -- the
     monoculture guard, and the reason E3 (Quality-Diversity) exists. A D1 pass bought by
     freezing the population is the §5.13 failure, not a result.

  python3 -u experiment_dose.py --seeds 40      # THE VERDICT (~110 min)
  python3 -u experiment_dose.py --seeds 3       # smoke test

VERDICT (virgin seeds 201-240, n=40):

  D1 THE LAND SELECTS     PASS  +0.0361 [CI +0.0055..+0.0668]  d +0.38  sign 27/40  p 0.019
  D2 IT BEATS DRIFT       FAIL  +0.0103 [CI -0.0168..+0.0374]  d +0.12  sign 21/40  p 0.437
  D3 VARIANCE SURVIVES    PASS  mean trait sd 0.161 (founding ~0.17), min 0.085

D1 is E2's deferred claim, settled: the CI now EXCLUDES zero, which is exactly what the
held-out five-seed run could not manage, and the effect size (d +0.38) landed where E2
registered it (~+0.45). Lean graded land selects the cheap-to-feed. The population
phenomenon is real at n=40.

D2 IS THE HONEST HOLE, and it is the more interesting number. The selected regimes differ
by no more than their own NO-SELECTION twins do (d +0.12, sign 21/40 -- a coin). So the
regimes diverge, but this experiment CANNOT show that the selection machinery is what
diverged them: the same gap appears with selection switched off. The likely reading is
that `press` shapes the population through channels that are not selection_enabled at all
-- lean land starves and kills regardless of the E2 gate, and hardship every 100 ticks
reshapes who breeds. That is still the ENVIRONMENT selecting, but it is not E2's mechanism
being demonstrated, and the two must not be conflated. A cleaner D2 needs an arm where the
land is lean but mortality is held fixed.

D3 clears the monoculture guard with room: trait sd holds at 0.161 against a founding
~0.17 (min 0.085), so nothing here was bought by freezing the population. E3
(Quality-Diversity) is not yet forced by the data.

Power note: the observed d +0.377 wants 57 seeds for 80% power (scripts/stats.power_n);
40 were run. D1 cleared its CI anyway, so it is not underpowered for the claim it makes
-- but a replication should budget 57+, not 40.
"""
from __future__ import annotations

import argparse
import statistics as st

from scripts.arena_harness import build, run
from scripts.arena_stats import genome_stats
from scripts.stats import paired, power_n, summary

TICKS = 2000
FOUNDERS = 24
DIAL = "metabolism"          # E2's registered trait: how fast a soul consumes stakes


def arm(seed: int, regime: str, selection: bool) -> dict:
    w = build(seed=seed, founders=FOUNDERS, regime=regime)
    w.selection_enabled = selection
    run(w, TICKS)
    row = genome_stats(w.agents, centre={})     # no drift column; absolute means only
    d = row["dials"].get(DIAL, {})
    return {"n": row["n"], "mean": d.get("mean"), "sd": d.get("sd")}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", type=int, default=40, help="how many virgin seeds")
    p.add_argument("--start", type=int, default=201, help="first seed (virgin band)")
    args = p.parse_args()
    seeds = list(range(args.start, args.start + args.seeds))
    print(f"=== E2 dose-response: does the land select {DIAL}? "
          f"({len(seeds)} seeds from {seeds[0]}, {TICKS} ticks, 4 arms each) ===\n")
    print(f"  target power: {power_n(0.45)} seeds for the registered d ~ 0.45\n")
    print(f"  {'seed':<6}{'press+sel':>11}{'watch+sel':>11}{'press-sel':>11}"
          f"{'watch-sel':>11}{'D1 delta':>10}{'sd(p+s)':>9}")
    ps, ws, pn, wn, alive = [], [], [], [], []
    for sd in seeds:
        a = arm(sd, "press", True)
        b = arm(sd, "watch", True)
        c = arm(sd, "press", False)
        d = arm(sd, "watch", False)
        if None in (a["mean"], b["mean"], c["mean"], d["mean"]):
            print(f"  {sd:<6}  (a town died out -- skipped)")
            continue
        ps.append(a["mean"]); ws.append(b["mean"])
        pn.append(c["mean"]); wn.append(d["mean"])
        alive.append(a["n"])
        print(f"  {sd:<6}{a['mean']:>+11.4f}{b['mean']:>+11.4f}{c['mean']:>+11.4f}"
              f"{d['mean']:>+11.4f}{b['mean'] - a['mean']:>+10.4f}{a['sd'] or 0:>9.3f}")

    if len(ps) < 2:
        print("\n  not enough completed seeds for a verdict")
        return
    # D1: watch - press, so a POSITIVE delta means press selected the lower metabolism
    d1 = paired([w - p_ for w, p_ in zip(ws, ps)], [0.0] * len(ps))
    print(f"\n  D1 press selects LOWER {DIAL} than watch (paired, watch - press):")
    print(f"     {d1}")
    # D2: does selection move a regime further than the no-selection twins differ?
    sel_gap = [abs(w - p_) for w, p_ in zip(ws, ps)]
    nul_gap = [abs(w - p_) for w, p_ in zip(wn, pn)]
    d2 = paired(sel_gap, nul_gap)
    print(f"  D2 selected regimes differ MORE than their drift twins do:")
    print(f"     {d2}")
    def verdict(pr):
        """PASS only when the 95% CI of the paired deltas EXCLUDES zero -- the bar E2's
        own held-out CI failed to clear, which is the whole reason this rerun exists."""
        ci = pr.effect.ci95
        return "PASS" if (pr.effect.mean > 0 and ci and ci[0] > 0) else "FAIL"

    for name, pr in (("D1 THE LAND SELECTS", d1), ("D2 IT BEATS DRIFT ", d2)):
        w, nz, pv = pr.sign
        print(f"     {name} : {verdict(pr)}   d {pr.d:+.3f}  sign {w}/{nz}  p {pv:.4f}")
    # D3: the monoculture guard -- variance must survive selection
    print(f"     D3 VARIANCE SURVIVES: reported per-seed in the sd column above")
    print(f"     mean town size: {st.fmean(alive):.0f} souls")


if __name__ == "__main__":
    main()
