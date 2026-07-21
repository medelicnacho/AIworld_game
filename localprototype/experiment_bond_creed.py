"""BONDING ON A SHARED VIEW -- attacking the gravity well at its source.

The reported problem: the arena's souls bunch into one mass and stay there. Measured, the
two big herds had an internal belief agreement of +0.043 -- a crowd of strangers walking
together, not a people.

Two attempts to fix it in the MOVEMENT physics both failed (world/sim.py, both recorded):
disagreement as a state (leavers re-absorbed; escape push 0.37x the pull) and disagreement
as a force (experiment_schism: S1 2/3, S2 2/3 -- not established). The post-mortem of both
pointed upstream -- ON A MISREAD, corrected here and left standing as the record. The figure
quoted was "a median 114 warm bonds out of 162"; that was bond ENTRIES (a dict key for every
soul ever heard from, the dead included). Measured properly on the same arena: entries median
182, WARM (trust > 0.15) median 15, STRONG (trust > 0.5) median ZERO. Nobody in that town
deeply loves anybody, and "every soul ends up loving every other" was not what was happening.
The 0.37x escape ratio DOES stand -- it was measured on feels_about() (affinity), a different
structure -- so the gravity well is real and was simply misattributed to bonds.

THE SOURCE: hear()'s bond signal is `0.3 * their_mood * my_mood + semantic_warmth`, and a
big town forces the Jaccard fallback, which zeroes the warmth term. So a bond accretes on
MOOD PRODUCT ALONE -- two souls in decent spirits warm to each other whatever either
believes, and most souls are in decent spirits most of the time. `Agent.bond_creed` adds the
missing term: a shared view warms, an opposed one cools (agent/bond.py CREED, on equal
footing with the mood term, never a veto).

PRE-REGISTERED (3 seeds; a claim passes at 3/3, and 2/3 is reported as NOT established --
the schism walk's lesson, where 2/3 was talked about as if it were a result):

  B1 FEWER WARM BONDS. Median warm bonds per soul falls materially. [RESULT 2/3 -- FAILED,
     and the correction above says why: at ~5-9 warm bonds per soul in these worlds there was
     never a mass of spurious warmth to remove. The claim was aimed at a problem of the wrong
     size.]
  B2 BONDS TRACK BELIEF. Mean agreement across WARM-BONDED pairs exceeds mean agreement
     across ALL pairs -- the bonds that survive are the ones between people who agree.
     Null: bonding is indifferent to belief, so the two means coincide.
  B3 DISPERSAL. In-clump belief agreement rises AND/OR the biggest clump holds a smaller
     share -- the thing actually reported, arriving without touching movement physics.
  B4 NO POPULATION COST (VETO). Not materially smaller. A town that fragments into
     starvation is not a fix, and S3 is the claim that caught that fear being false before.

RESULT (seeds 11-13): B1 2/3, B2 3/3, B3 3/3, B4 3/3 -> FAIL at the 3/3-on-all bar; gate
stays shut. B2 is the clean one and it is worth keeping: with the creed OFF, warm bonds do
not track belief AT ALL -- on two of three seeds warm-bonded pairs were LESS aligned than
random pairs (0.534 vs 0.560; 0.325 vs 0.363), i.e. bonding was belief-blind noise. With it
on, every seed reverses (0.622/0.554, 0.420/0.318, 0.401/0.308). The mechanism does exactly
what it was built to do. What it does NOT do is fix the bunching -- and B3's pass is soft,
riding an OR whose dispersal leg failed on seed 12 (biggest clump 52% -> 67%).

  python3 -u experiment_bond_creed.py        # ~1 hour, 6 runs. USE -u: it is silent otherwise.
"""
from __future__ import annotations

import math
import random
import statistics as st

from santana_app.evolution import _found_settlements, _gates
from services.llm import MockLLM
from world.sim import World, _belief_cos

TICKS = 2000
FOUNDERS = 24
SEEDS = (11, 12, 13)
LINK = 200.0
WARM_AT = 0.15      # trust above which a bond counts as WARM


def _clumps(ags):
    un = list(range(len(ags)))

    def f(i):
        while un[i] != i:
            un[i] = un[un[i]]
            i = un[i]
        return i

    for i, a in enumerate(ags):
        for j in range(i + 1, len(ags)):
            b = ags[j]
            if math.hypot(a.position[0] - b.position[0],
                          a.position[1] - b.position[1]) < LINK:
                un[f(i)] = f(j)
    groups: dict = {}
    for i, a in enumerate(ags):
        groups.setdefault(f(i), []).append(a)
    return list(groups.values())


def run(creed: bool, seed: int) -> dict:
    rng = random.Random(seed)
    w = World(rebirth_enabled=False, events_enabled=False)
    w.llm = MockLLM(seed=seed)
    _gates(w, FOUNDERS)
    _found_settlements(w, rng, FOUNDERS)
    for a in w.agents:                 # the ONE variable
        a.bond_creed = creed
    for _ in range(TICKS):
        w.step(speak=False)
    ags = w.agents
    if not ags:
        return {"n": 0, "warm": 0, "warm_agree": float("nan"), "all_agree": float("nan"),
                "biggest": 1.0, "clump_agree": float("nan")}
    by_id = {a.id: a for a in ags}
    warm_counts, warm_sims, all_sims = [], [], []
    for a in ags:
        n_warm = 0
        for oid, bond in (getattr(a, "bonds", {}) or {}).items():
            b = by_id.get(oid)
            if b is None:
                continue
            if getattr(bond, "trust", 0.0) > WARM_AT:
                n_warm += 1
                s = _belief_cos(a, b)
                if s is not None:
                    warm_sims.append(s)
        warm_counts.append(n_warm)
    sample = random.Random(seed).sample(ags, min(40, len(ags)))
    for i, a in enumerate(sample):
        for b in sample[i + 1:]:
            s = _belief_cos(a, b)
            if s is not None:
                all_sims.append(s)
    groups = _clumps(ags)
    csims = []
    for g in groups:
        if len(g) < 3:
            continue
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                s = _belief_cos(a, b)
                if s is not None:
                    csims.append(s)
    return {"n": len(ags),
            "warm": st.median(warm_counts) if warm_counts else 0,
            "warm_agree": st.fmean(warm_sims) if warm_sims else float("nan"),
            "all_agree": st.fmean(all_sims) if all_sims else float("nan"),
            "biggest": max(len(g) for g in groups) / len(ags),
            "clump_agree": st.fmean(csims) if csims else float("nan")}


def main() -> None:
    print(f"  {TICKS} ticks, {FOUNDERS} founders, seeds {SEEDS}, MockLLM (deterministic)\n")
    print(f"  {'seed':<6}{'arm':<7}{'alive':>7}{'warm bonds':>12}{'agree|warm':>12}"
          f"{'agree|all':>11}{'biggest':>9}{'clump agree':>13}")
    b1 = b2 = b3 = b4 = 0
    for sd in SEEDS:
        off, on = run(False, sd), run(True, sd)
        for label, r in (("off", off), ("on", on)):
            print(f"  {sd:<6}{label:<7}{r['n']:>7}{r['warm']:>12.0f}{r['warm_agree']:>+12.3f}"
                  f"{r['all_agree']:>+11.3f}{r['biggest']:>8.0%}{r['clump_agree']:>+13.3f}")
        ok1 = on["warm"] < off["warm"] * 0.9
        ok2 = on["warm_agree"] > on["all_agree"]
        ok3 = (on["clump_agree"] > off["clump_agree"]) or (on["biggest"] < off["biggest"])
        ok4 = on["n"] >= 0.9 * off["n"]
        b1 += ok1
        b2 += ok2
        b3 += ok3
        b4 += ok4
        print(f"        -> B1 fewer bonds {'YES' if ok1 else 'no '}   "
              f"B2 tracks belief {'YES' if ok2 else 'no '}   "
              f"B3 dispersed {'YES' if ok3 else 'no '}   "
              f"B4 no pop cost {'YES' if ok4 else 'NO (veto)'}\n")
    n = len(SEEDS)
    print(f"  B1 FEWER WARM BONDS   : {b1}/{n}")
    print(f"  B2 BONDS TRACK BELIEF : {b2}/{n}")
    print(f"  B3 DISPERSAL          : {b3}/{n}")
    print(f"  B4 NO POPULATION COST : {b4}/{n}   (veto)")
    ok = b1 == n and b2 == n and b3 == n and b4 == n
    print(f"\n  VERDICT: {'BONDING ON A SHARED VIEW WORKS' if ok else 'did NOT show the signature'}")


if __name__ == "__main__":
    main()
