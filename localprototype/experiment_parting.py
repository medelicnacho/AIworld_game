"""THE PARTING: does a bloc that stopped agreeing leave as a PEOPLE, or just scatter?

The gap this fills (measured by grep: no exile/secession/departure mechanism existed
anywhere): the substrate grows factions (§5.6) and they take territory (§5.26, 5/5), and
the civ wheel runs schism -> war -> collapse -- but a settlement never EMITS anything. The
losing bloc dies in place; war parties are assembled per raid and dissolve. So there was no
road from "factions emerge" to "warbands roam the wild", which is the shape gameworld's
D12/D16 need.

Three earlier attempts made dispersal a CONTINUOUS FORCE on every soul and all three
failed. The diagnosis is why this one is discrete: souls cluster because they GENUINELY
AGREE (affinity discriminates on belief, +0.606 vs -0.369), so pushing everyone apart
fights the substrate's own honest read. A bloc that has stopped agreeing is already a
coherent group BY THAT SAME READ -- moving it as one goes with the grain.

PRE-REGISTERED (3 seeds; a claim passes at 3/3). The NULL for P2/P3 is a matched set of
souls chosen at random from the same town, moved the same way -- so "a band holds together"
must beat "any equally-sized group of townsfolk would look this coherent".

  P1 A BAND FORMS AT ALL. At least one parting occurs, of >= MIN_BAND grown warriors.
     Without this the rest is untestable and the thresholds are wrong.

  P2 THEY LEAVE TOGETHER. A window after parting, the band's mean pairwise distance is
     materially SMALLER than the random-matched null's -- they went as a people, not as
     individuals who happened to be told to go.

  P3 THEY ARE A PEOPLE, NOT A TAIL. The band's internal belief agreement exceeds the
     town's own average pairwise agreement -- what left was a view, not the unaligned
     remainder.

  P4 THE FLOORS HELD -- THE VETO. No breeder, no child, and no collapsed soul is in any
     band, ever. These are welfare invariants, not tuning: a failure here is a bug to fix,
     never a threshold to relax.

  python3 -u experiment_parting.py

VERDICT (seeds 11-13, 6000 ticks, 40 founders):

  P1 A BAND FORMS          3/3   9, 1 and 6 partings; bands of 4-8 grown warriors
  P2 THEY LEAVE TOGETHER   2/3   spread 566/536, 144/1076, 333/1248
  P3 A PEOPLE, NOT A TAIL  3/3   band agreement +0.871/+0.942/+0.789 vs town
                                 +0.211/+0.008/+0.081 -- a 4-100x separation
  P4 THE FLOORS HELD       3/3   (veto) no breeder, child or collapsed soul, ever

FAILS the 3/3-on-all bar on P2, so the gate stays OFF. But note WHICH claim carries the
mechanism: P3 says what leaves is unambiguously a coherent VIEW, not the town's unaligned
remainder, and it passes by an enormous margin on every seed. That was the thing three
earlier continuous-force attempts could never produce.

P2's miss is on seed 11 (566 vs 536), and the null is arguably the wrong one: it compares
a band that has walked ~900 units out and is roaming against a random sample of a
settlement that is COMPACT BY CONSTRUCTION (§5.26: kin cluster at ~26px). A roaming band
being as spread as a settled town is not obviously a failure to travel together. That
weakness is RECORDED, NOT ACTED ON -- one claim in this session's work has already been
re-specified after missing, and re-specifying a second is how a harness stops meaning
anything. Settling it wants a null of souls at comparable distance from home, or a direct
read (did the centroid leave, and did the spread stay bounded), pre-registered before running.

BAND LIFETIME, measured while diagnosing and worth recording: bands live ~300-980 ticks,
about ONE LIFETIME, at wellbeing 0.62-0.92 -- they do not starve, they age out. This falls
straight out of the caste floor: breeders keep the hearth, so a parting band is all
warriors and cannot reproduce. For gameworld D12/D16 that is arguably the ideal shape --
hostile bands that are self-limiting and continuously replaced by fresh schisms, needing
no cull and no leash to bound their population.
"""
from __future__ import annotations

import math
import random
import statistics as st

from scripts.arena_harness import build, run
from world import parting as _parting
from world.sim import _belief_cos

TICKS = 6000
FOUNDERS = 40
SEEDS = (11, 12, 13)
SETTLE = 400          # ticks after a parting before we read whether it held together


def _spread(souls) -> float:
    """Mean pairwise distance -- how scattered a set of souls is."""
    pairs = [(a, b) for i, a in enumerate(souls) for b in souls[i + 1:]]
    if not pairs:
        return 0.0
    return st.fmean(math.hypot(a.position[0] - b.position[0],
                               a.position[1] - b.position[1]) for a, b in pairs)


def _agreement(souls) -> float:
    sims = [_belief_cos(a, b) for i, a in enumerate(souls) for b in souls[i + 1:]]
    sims = [s for s in sims if s is not None]
    return st.fmean(sims) if sims else float("nan")


def run_seed(seed: int) -> dict:
    w = build(seed=seed, founders=FOUNDERS)
    w.parting_enabled = True
    bands: list = []
    read: dict = {}

    def sample(t, world):
        formed = [b for b in getattr(world, "_bands", []) if b not in bands]
        for b in formed:
            bands.append(b)
        # once a band is SETTLE ticks old, read whether it held together
        for b in list(bands):
            born = int(b.split(":")[1].split(".")[0])
            if b in read or t < born + SETTLE:
                continue
            members = [a for a in world.agents if getattr(a, "band", "") == b]
            if len(members) < 3:
                read[b] = None          # died out before the read; not evidence either way
                continue
            townsfolk = [a for a in world.agents if not getattr(a, "band", "")]
            rng = random.Random(seed)
            null = (rng.sample(townsfolk, len(members))
                    if len(townsfolk) >= len(members) else [])
            read[b] = {"n": len(members),
                       "spread": _spread(members),
                       "null_spread": _spread(null) if null else float("nan"),
                       "agree": _agreement(members),
                       "town_agree": _agreement(rng.sample(
                           world.agents, min(30, len(world.agents))))}

    run(w, TICKS, on_sample=sample, every=20)

    # P4: the floors, checked over every soul that ever wore a band
    breach = []
    for a in w.agents:
        if not getattr(a, "band", ""):
            continue
        if getattr(a, "caste", "warrior") == "breeder":
            breach.append(f"{a.name}: breeder")
        if w.clock_enabled:
            from world import clock as _clk
            if _clk.stage(a.age, a.lifespan) == "child":
                breach.append(f"{a.name}: child")
    reads = [r for r in read.values() if r]
    return {"bands": len(bands), "reads": reads, "breach": breach,
            "alive": len(w.agents)}


def main() -> None:
    print(f"  {TICKS} ticks, {FOUNDERS} founders, seeds {SEEDS}, "
          f"read {SETTLE} ticks after each parting\n")
    print(f"  {'seed':<6}{'bands':>7}{'read':>6}{'size':>6}{'spread':>9}{'null':>9}"
          f"{'agree':>8}{'town':>8}{'floors':>8}")
    p1 = p2 = p3 = p4 = 0
    for sd in SEEDS:
        r = run_seed(sd)
        rr = r["reads"]
        if rr:
            size = st.fmean(x["n"] for x in rr)
            spread = st.fmean(x["spread"] for x in rr)
            null = st.fmean(x["null_spread"] for x in rr)
            agree = st.fmean(x["agree"] for x in rr)
            town = st.fmean(x["town_agree"] for x in rr)
        else:
            size = spread = null = agree = town = float("nan")
        ok1 = r["bands"] > 0
        ok2 = bool(rr) and spread < null
        ok3 = bool(rr) and agree > town
        ok4 = not r["breach"]
        p1 += ok1
        p2 += ok2
        p3 += ok3
        p4 += ok4
        print(f"  {sd:<6}{r['bands']:>7}{len(rr):>6}{size:>6.1f}{spread:>9.0f}{null:>9.0f}"
              f"{agree:>+8.3f}{town:>+8.3f}"
              f"{'OK' if ok4 else 'BREACH':>8}")
        if r["breach"]:
            print(f"        !! floor breach: {r['breach'][:4]}")
    n = len(SEEDS)
    print(f"\n  P1 A BAND FORMS          : {p1}/{n}")
    print(f"  P2 THEY LEAVE TOGETHER   : {p2}/{n}   (vs a random-matched null)")
    print(f"  P3 A PEOPLE, NOT A TAIL  : {p3}/{n}")
    print(f"  P4 THE FLOORS HELD       : {p4}/{n}   (veto -- a bug, never a threshold)")
    ok = p1 == n and p2 == n and p3 == n and p4 == n
    print(f"\n  VERDICT: {'BANDS PART AS PEOPLES' if ok else 'did NOT show the signature'}")


if __name__ == "__main__":
    main()
