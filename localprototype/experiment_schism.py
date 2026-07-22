"""
!!! BOTH VERDICTS BELOW ARE VOID -- THE HARNESS WAS BROKEN TWICE OVER. !!!

1. NONDETERMINISM. World defaults move_seed=None -> random.Random(None) -> the movement
   RNG is seeded from OS ENTROPY. Every run in this file was built as
   World(rebirth_enabled=False, events_enabled=False) with no move_seed, so the same
   "seed" produced a different world every time: three identical calls gave 60 / 56 / 46
   souls alive. Every per-seed on-vs-off comparison here is therefore a comparison of two
   DIFFERENT worlds, and the pass/fail counts measure run-to-run noise as much as any
   mechanism. Fixed below (move_seed=seed); the recorded numbers are NOT re-run.

2. NO OPINION DYNAMICS. w.step(speak=False) makes ZERO hear() calls -- measured: 300
   ticks, 0 hear(), 0 _bounded_confidence(). The live arena speaks through a separate
   speak_turn() thread, which nothing here calls. So beliefs never assimilated, never
   repelled, never individuated; they changed ONLY by inheritance-with-noise at birth.
   Every mechanism tested here reads belief, and none of them was tested against a
   living opinion landscape. Headless-with-speak=False is NOT the arena.

What still stands: the DIAGNOSTIC measurements (taken on saved snapshots, not on these
runs) -- the +0.043 in-clump agreement, the 0.37x escape ratio, the affinity decomposition,
the bimodal belief histogram. Those were reads of a real running town and are unaffected.

THE SCHISM WALK FALSIFIER -- clean room, pre-registered, seeded.

The first two reads were both confounded: one ran a FRESH world too short (700 ticks, where
settlements are still like-minded at +0.690 and the mechanic correctly does nothing), the
other forked the LIVE arena mid-collapse (147 -> ~60 souls in both arms, so dispersal could
not be told from dying). This runs both arms from founding, same seed per pair, long enough
for the mixing to actually develop.

PRE-REGISTERED (a claim passes at >= 4/5 arms; here 3 seeds, so >= 3/3 or 2/3 noted honestly):

  S1 LIKE-MINDED CLUMPS. In-clump belief agreement is HIGHER with the schism walk on.
     This is the mechanic's actual job: a clump should be a people, not a crowd.
  S2 DISPERSAL. The biggest clump holds a SMALLER share of the town, and/or more of the
     24 regions are occupied. This is the thing the user reported and the state machine
     failed to deliver.
  S3 NO POPULATION COST (the viability guard). The town is not meaningfully smaller with
     the mechanic on. Dispersal that scatters souls away from food and hearths until they
     die is not a fix -- and the first fork showed 53 alive against 65, which is exactly
     the failure this claim exists to catch.

S3 is a VETO: S1 and S2 passing while S3 fails means the mechanic works by killing people.

RESULT (seeds 11-13): S1 2/3, S2 2/3, S3 3/3 -> FAIL at the pre-registered bar. The effect
looks CONDITIONAL on how bunched the town already was -- seed 12's off-arm was one clump at
100% and the walk helped most (agreement +0.300 -> +0.504, biggest 100% -> 66%); seed 11's
off-arm was already well split (5 clumps, 53%) and the walk made it WORSE (biggest -> 99%).
At n=3 with a sign flip that is a hypothesis, not a finding, and the mechanic stays OFF.

S3 is the one clean result and it EXONERATES an earlier worry: the first fork showed 53 alive
against 65 and looked like the walk was scattering souls until they starved. It was not -- that
fork started from a world already collapsing in BOTH arms. Run clean, the walk costs nothing:
98/99, 113/102, 114/106. Dispersal is not killing anybody.

  python3 experiment_schism.py        # ~1 hour, 6 runs; use -u, it is silent otherwise
"""
import math
import statistics as st
import sys

from scripts.arena_harness import build
from scripts.arena_harness import run as run_arena
from world.sim import _belief_cos                              # noqa: E402

TICKS = 2000
FOUNDERS = 24
SEEDS = (11, 12, 13)
LINK = 200.0        # single-link radius for "a clump"


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
    groups = {}
    for i, a in enumerate(ags):
        groups.setdefault(f(i), []).append(a)
    return list(groups.values())


def run(schism, seed):
    # built and run through the ONE correct door: move_seed wired (or the movement
    # RNG comes from OS entropy) and speech running (or hear() never fires and the
    # opinion dynamics this reads are dead). Both faults voided this file once.
    w = build(seed=seed, founders=FOUNDERS)
    w.schism_walk = schism
    run_arena(w, TICKS)
    ags = w.agents
    if not ags:
        return {"n": 0, "clumps": 0, "biggest": 1.0, "regions": 0, "agree": float("nan")}
    groups = _clumps(ags)
    sims = []
    for g in groups:
        if len(g) < 3:
            continue
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                s = _belief_cos(a, b)
                if s is not None:
                    sims.append(s)
    cells = {(min(5, int(a.position[0] / 600)), min(3, int(a.position[1] / 600)))
             for a in ags}
    return {"n": len(ags), "clumps": len(groups),
            "biggest": max(len(g) for g in groups) / len(ags),
            "regions": len(cells),
            "agree": st.fmean(sims) if sims else float("nan")}


print(f"  {TICKS} ticks, {FOUNDERS} founders, seeds {SEEDS}, MockLLM (deterministic)\n")
print(f"  {'seed':<6}{'arm':<8}{'alive':>7}{'clumps':>8}{'biggest':>9}"
      f"{'regions':>9}{'in-clump agree':>16}")
s1 = s2 = s3 = 0
for sd in SEEDS:
    off, on = run(False, sd), run(True, sd)
    for label, r in (("off", off), ("on", on)):
        print(f"  {sd:<6}{label:<8}{r['n']:>7}{r['clumps']:>8}{r['biggest']:>8.0%}"
              f"{r['regions']:>9}{r['agree']:>+16.3f}")
    ok1 = on["agree"] > off["agree"]
    ok2 = on["biggest"] < off["biggest"] or on["regions"] > off["regions"]
    ok3 = on["n"] >= 0.9 * off["n"]
    s1 += ok1
    s2 += ok2
    s3 += ok3
    print(f"        -> S1 like-minded {'YES' if ok1 else 'no '}   "
          f"S2 dispersed {'YES' if ok2 else 'no '}   "
          f"S3 no pop cost {'YES' if ok3 else 'NO (veto)'}\n")
n = len(SEEDS)
print(f"  S1 LIKE-MINDED CLUMPS : {s1}/{n}")
print(f"  S2 DISPERSAL          : {s2}/{n}")
print(f"  S3 NO POPULATION COST : {s3}/{n}   (veto: S1+S2 mean nothing if this fails)")
ok = s1 == n and s2 == n and s3 == n
print(f"\n  VERDICT: {'THE SCHISM WALK WORKS' if ok else 'did NOT show the signature'}")
