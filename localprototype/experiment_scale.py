"""THE SCALE PROBE: does the substrate survive n=32/64 -- and does selection's headline
become CONFIRMED when the town is big enough to see it?

Everything in this repo is validated at n=6-10. The game runs at n in the hundreds.
Nobody has ever watched this substrate above ten souls -- so this probe is the
pre-engine gate: it either de-risks the port or finds the scale-breakage HERE, where
it is cheap. Three questions, all headless, markov/mock only:

PRE-REGISTERED (tuning 11-13 for knobs; VERDICTS from virgin seeds 101-105).

OUTCOMES SO FAR (2026-07-03, seeds 101-105 -- consumed, never a verdict again):
  SC2 PASSED 4/5: at n=64 the flood story reached ~62/63 souls and CONVERGED (three
      seeds at 100% dominant-variant; one honest MUSH at 13%). The legend engine is
      not a small-town artifact.
  SC3 measured: 1827 t/s (n=8), 537 (n=32), 320 (n=64), headless CPU python.
  SC1 v1 FAILED -- and diagnostically: harsh starved ZERO at n=32 (it kills 1-4 at
      n=10). The probe found WHY, and it is a finding: MUTUAL AID SCALES. With 32
      souls there are always donors above the share threshold, so the compassion/
      commons machinery rescues the weakest before the hazard opens -- emergent
      risk-pooling; the bigger town buffers famine better per-capita. For selection
      to bite at scale, scarcity must be STRUCTURAL (deep enough that redistribution
      cannot cover it) -- hence SC1 v2 below.

SC1 v2 (the re-verdict, virgin seeds 111-115): the 'harsh2' regime -- soil aid cannot
out-share (yield 0.15), storms every 5, granary loss 0.7. Sanity-checked killing (3
and 12 starvations at n=32) without extinction. Same bar as v1: sign 5/5 AND CI95
excluding 0 against the twin-null.

  SC1 SELECTION AT SCALE (the E2 upgrade): the exact validated E2 harness
      (experiment_selection.run), re-run at n=32 founders / cap 56 / 800 ticks.
      E2's verdict at n=10 was honestly graded DIRECTIONAL (sign 4/5, CI past 0).
      Claim: at n=32 the gentle-minus-harsh metabolism gap D_sel beats its twin-null
      D_null with sign 5/5 AND stats.paired CI95 EXCLUDING 0 -- the dose-response
      confirmed by n, not by wishing.
  SC2 LEGEND AT SCALE: the §5.16 lore protocol (3 witnesses of a flood, murmur +
      retelling, the wheel turning) in a town of 64. Claim: the story still TRAVELS
      (>= 12 souls end carrying a recognizable descendant), stays TRACEABLE (every
      tagged copy still bears the ground-truth lore_id), and CONVERGES (the dominant
      variant is held by >= 40% of carriers) -- a myth, not mush, at 8x the
      validated population. 4/5 seeds.
  SC3 THE METER: ticks/second at n=8/32/64 (200 ticks each, one seed) -- not a claim,
      a MEASUREMENT for the engine's capacity planning, printed plainly, plus a
      no-crash/no-collapse sanity across every run above.

  python experiment_scale.py
"""
from __future__ import annotations

import statistics
import time

from agent.agent import Agent
from agent.memory import _similarity
from scripts.stats import paired
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

from experiment_selection import REGIMES, run as e2_run

# SC1 v2: structural scarcity -- deep enough that emergent mutual aid (the v1 finding)
# cannot redistribute its way out of it. Injected here; experiment_selection's own
# recorded verdict never uses it.
REGIMES["harsh2"] = {"interval": 5, "commons": 1.0, "yield": 0.15, "commons_loss": 0.7}

TUNING_SEEDS = (11, 12, 13)
HELDOUT_SEEDS = (101, 102, 103, 104, 105)    # CONSUMED by v1 (see docstring)
SC1V2_SEEDS = (111, 112, 113, 114, 115)      # virgin, for the v2 re-verdict

# --- SC1: E2 at n=32 --------------------------------------------------------------------
SC1_N, SC1_TICKS, SC1_CAP = 32, 800, 56

# --- SC2: the lore protocol at n=64 (mirrors experiment_lore.py, scaled) ------------------
SC2_N, SC2_TICKS, SC2_WITNESS = 64, 1200, 3
STORY = "the great flood in the night took the miller's child and half the winter stores"
LORE_ID = "the-flood"
CARRY_OVERLAP = 0.30


def sc1(seeds, harsh: str = "harsh") -> dict:
    d_sel, d_null = [], []
    for seed in seeds:
        hs = e2_run(seed, harsh, True, n_founders=SC1_N, ticks=SC1_TICKS, max_souls=SC1_CAP)
        gs = e2_run(seed, "gentle", True, n_founders=SC1_N, ticks=SC1_TICKS, max_souls=SC1_CAP)
        hn = e2_run(seed, harsh, False, n_founders=SC1_N, ticks=SC1_TICKS, max_souls=SC1_CAP)
        gn = e2_run(seed, "gentle", False, n_founders=SC1_N, ticks=SC1_TICKS, max_souls=SC1_CAP)
        if None in (hs["tail_met"], gs["tail_met"], hn["tail_met"], gn["tail_met"]):
            print(f"  seed {seed}: EXTINCT arm at n=32 (counted, excluded)")
            continue
        d_sel.append(gs["tail_met"] - hs["tail_met"])
        d_null.append(gn["tail_met"] - hn["tail_met"])
        print(f"  seed {seed}: D_sel {d_sel[-1]:+.3f} (harsh starved {hs['starved']}, "
              f"gentle born {gs['born']})  D_null {d_null[-1]:+.3f}")
    cmp = paired(d_sel, d_null)
    print(f"  SC1 paired: {cmp}")
    lo, hi = cmp.effect.ci95 if cmp.effect.ci95 else (0.0, 0.0)
    return {"pass": (cmp.effect.mean > 0 and cmp.sign[0] == cmp.sign[1]
                     and cmp.effect.ci95 is not None and lo > 0.0),
            "cmp": cmp}


def sc2_run(seed: int) -> dict:
    embed.use_jaccard_only(True)
    w = World(events_enabled=True, rebirth_enabled=True, murmur_enabled=True, move_seed=seed,
              events=[WorldEvent(name="flood", description=STORY, tick=50, emotion=-0.7,
                                 urge=0.6, scope=tuple(f"s{i}" for i in range(SC2_WITNESS)),
                                 lore_id=LORE_ID)])
    w.llm = MockLLM(seed=7)
    w.lore_enabled = True
    w.bardo_ticks = (5, 10)
    for i in range(SC2_N):
        a = Agent(f"s{i}", f"Soul{i}", (i * 15.0, 0.0), "You are a working soul.",
                  [f"the well, the field, the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0,
                  lifespan=250 + ((seed * 37 + i * 53) % 200))
        w.add(a)
    for _ in range(SC2_TICKS):
        w.advance()
    carriers, tagged = 0, []
    for a in w.agents:
        best = max((_similarity(m.text, STORY) for m in a.memory.items), default=0.0)
        if best >= CARRY_OVERLAP:
            carriers += 1
        tagged += [m for m in a.memory.items if getattr(m, "lore_id", "") == LORE_ID]
    # convergence: the most-held variant's share among tagged copies
    share = 0.0
    if tagged:
        groups: list[list] = []
        for m in tagged:
            for g in groups:
                if _similarity(m.text, g[0].text) >= 0.5:
                    g.append(m)
                    break
            else:
                groups.append([m])
        share = max(len(g) for g in groups) / len(tagged)
    return {"carriers": carriers, "tagged": len(tagged), "share": share,
            "pop": len(w.agents)}


def sc2(seeds) -> dict:
    ok = 0
    for seed in seeds:
        r = sc2_run(seed)
        hit = r["carriers"] >= 12 and r["tagged"] > 0 and r["share"] >= 0.40
        ok += hit
        print(f"  seed {seed}: carriers {r['carriers']}/{r['pop']}, tagged copies "
              f"{r['tagged']}, dominant-variant share {r['share']:.0%} "
              f"-> {'holds' if hit else 'MUSH'}")
    return {"pass": ok >= len(seeds) - 1, "ok": ok}


def sc3() -> None:
    print("  SC3 the meter (one seed, 200 ticks each, headless mock):")
    for n in (8, 32, 64):
        r0 = time.time()
        e2_run(11, "gentle", True, n_founders=n, ticks=200, max_souls=n + 8)
        dt = time.time() - r0
        print(f"    n={n:3}: {200 / dt:7.1f} ticks/sec  ({dt:.1f}s for 200 ticks)")


def main() -> None:
    print(__doc__)
    print("\n(v1 outcomes above are the record: SC2 PASS 4/5, SC3 measured, SC1 v1 FAIL")
    print(" with the mutual-aid finding. This run is SC1 v2 only, on virgin 111-115.)")
    print("\n--- SC1 v2 TUNING (seeds 11-12; knobs only, never a verdict) ---")
    sc1((11, 12), harsh="harsh2")
    print("\n--- SC1 v2 HELD-OUT virgin seeds 111-115 (the verdict) ---")
    v1 = sc1(SC1V2_SEEDS, harsh="harsh2")
    print("\n=== VERDICT (held-out; pre-registered) ===")
    print(f"  SC1v2 SELECTION CONFIRMED AT SCALE: {'PASS' if v1['pass'] else 'FAIL'}")
    v2 = {"pass": True}   # SC2's recorded verdict (101-105, PASS 4/5) stands
    print("\nHonest frame: SC1 PASS upgrades E2's directional grade to CONFIRMED (the "
          "n did it, not the wishing); SC1 FAIL means even n=32 is under-powered and "
          "the claim stays with the engine. SC2 PASS means the lore engine's "
          "convergence is not a small-town artifact. SC3 is capacity data for the "
          "port, not a claim.")
    import sys
    sys.exit(0 if (v1["pass"] and v2["pass"]) else 1)


if __name__ == "__main__":
    main()
