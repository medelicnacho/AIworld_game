"""DOES THE SUBSTRATE SURVIVE GAME TIME? The rescale nobody has checked.

gameworld/STAGES.md §3 names this the big one, and the arithmetic is worse than it looks:

    a graced memory (decay 0.995) falls under FORGET_THRESHOLD after ~402 ticks

    lifespan    60  (lab default)  -> a memory spans 670% of a life
    lifespan  1150  (the arena)    -> 35%
    lifespan 35000  (game spans)   -> 1.1%

Every validated result was measured where a memory outlasts, or is a large fraction of, a
whole life. At game spans a soul's memory horizon turns over ~87 times before it dies. That
is not the same mind with a longer clock; it is a different mind, and bonds, lore, identity
and grudges all key off memory.

Nothing in the substrate ASSUMES a scale -- but nothing has ever RUN at this one either.

PRE-REGISTERED (3 lifespan scales, same seed, same everything else; each arm runs 1.2
lifespans so souls are compared at the same point in their lives, not the same tick):

  T1 A SOUL STILL HAS A PAST. Mean memory items per soul at game span is at least half the
     arena's. A soul whose memory empties between events has no inner life to read.

  T2 BONDS SURVIVE THEIR OWN MEMORIES. Warm bonds per soul hold up at game span. Bond trust
     is stored on the Bond, not in memory -- so this SHOULD survive, and if it does not the
     coupling is somewhere nobody has mapped.

  T3 A LEGEND OUTLIVES ITS WITNESSES -- the keystone at risk. A story seeded at t=0 is still
     carried by souls at the end. §5.16 is the most memory-dependent validated result in the
     repo, and 402 ticks of memory against a 35000-tick life is exactly the condition it was
     never tested under.

  T4 FACTIONS STILL FORM. Blocs at game span, not one blob and not all loners. Opinion
     vectors are not memory-stored, so this is the control: if T4 also collapses, the cause
     is not memory horizon and the whole diagnosis is wrong.

  python3 -u experiment_gamespan.py

VERDICT (seed 11, 14 founders, 1.2 lifespans per arm):

  scale   lifespan   alive   items/soul   warm   blocs  biggest   horizon
  arena       1150     103        39.5    30.3      2       85     60.5%
  mid         8000      76       119.0    23.2      2       75     41.8%
  game       35000     108       457.9    27.3      2       94     18.9%

  T1 A SOUL STILL HAS A PAST      PASS   (more, not less -- the hypothesis was backwards)
  T2 BONDS SURVIVE THEIR MEMORIES PASS   (27.3 vs 30.3)
  T4 FACTIONS STILL FORM          PASS   (2 real camps, biggest 94 of 108)
  T3 A LEGEND OUTLIVES ITS TELLERS FAIL  -- but 0% in the ARENA CONTROL too, so this claim
     measured the setup, not the substrate. Seeding one story at t=0 does not exercise
     lore.py's retelling machinery, which is what §5.16's convergence actually rides on.
     Uninformative in both directions; a real version has to drive retellings.

THE BEHAVIOUR SURVIVES GAME TIME. THE BUDGET DOES NOT. Memory per soul rises 11.6x, and
against gameworld PLAN §3's own capacity law (~14us per item per tick) a 40-soul shard goes:

    arena   39.5 items ->  22 ms/tick
    mid    119.0 items ->  67 ms/tick
    game   457.9 items -> 256 ms/tick     against a 100ms budget at 10Hz

So a settlement shard at game lifespans exceeds its frame budget by ~2.5x. That is the
number PLAN §3 exists to protect, measured at the scale the game intends to run rather than
the scale the lab ran. STAGES.md §3a plans to LOG memory-items/tick against the law; this
says it should be a GATE, because the default configuration fails it.

The other half of the finding is the HORIZON: 60.5% -> 18.9% of a life. Not amnesia -- a
villager with a great deal to say and no long view, vivid about the last hour and blank
about its youth. Whether that is a bug or simply what a long-lived person is like is a
design question, but it is a different mind from the one every experiment measured.

Lifespan is therefore a design lever with a measured price, not a free choice: 20k buys a
~40-minute life at roughly a third of 50k's memory cost.

TWO BUGS IN THIS FILE'S OWN FIRST VERSION, both caught by the control:
  * it hand-rolled a town instead of using the harness, so the ARENA arm -- the validated
    configuration -- returned 0 warm bonds, 0% legend and every soul its own faction. A
    hand-rolled town lacks hearing_range 260 (souls could not hear each other), the shared
    per-settlement belief base, and stakes. A comparison whose control cannot reproduce the
    validated behaviour measures nothing, and it was the control that said so.
  * the rescale overwrote a.lifespan BEFORE using it to scale a.age, making the scaling a
    no-op; and the horizon subtracted memory created_tick from the SOUL'S AGE, two different
    clocks, which produced negative horizons.
"""
from __future__ import annotations

import statistics as st

from scripts.arena_harness import build, run
from world.factions import factions_of

N = 14
SEED = 11
SCALES = (("arena", 1150), ("mid", 8000), ("game", 35000))
LIVES = 1.2          # each arm runs this many lifespans, so souls are the same AGE
LEGEND = "the flood took the low houses and we carried what we could"


def run_scale(lifespan: int) -> dict:
    # Built through the ARENA HARNESS, not by hand. The first version hand-rolled a town and
    # its CONTROL ARM FAILED -- the arena scale, the validated configuration, showed 0 warm
    # bonds, 0% legend and every soul its own faction. A hand-rolled town is missing what
    # build() supplies: hearing_range 260 (souls could not hear each other at the World
    # default), one shared belief base per settlement plus noise, stakes and murmur. A
    # comparison whose control cannot reproduce the validated behaviour measures nothing.
    # LIFESPAN is the only variable: everything else is the arena, exactly.
    w = build(seed=SEED, founders=N)
    for a in w.agents:
        old = max(1, a.lifespan)        # capture BEFORE overwriting, or the scaling is a no-op
        a.age = int(a.age * lifespan / old)   # keep them at the same life-stage
        a.lifespan = lifespan
    for a in w.agents:
        a.memory.write(LEGEND, tick=0, source="event", emotion=-0.6,
                       weight=1.2, lore_id="flood")

    ticks = int(lifespan * LIVES)
    run(w, ticks)
    ags = w.agents
    if not ags:
        return {"ticks": ticks, "alive": 0}
    items = st.fmean(len(a.memory.items) for a in ags)
    warm = st.fmean(sum(1 for b in (getattr(a, "bonds", {}) or {}).values()
                        if getattr(b, "trust", 0.0) > 0.15) for a in ags)
    carriers = sum(1 for a in ags
                   if any(getattr(m, "lore_id", "") == "flood" for m in a.memory.items))
    facs = [f for f in factions_of(w).values() if f >= 0]
    sizes: dict = {}
    for f in facs:
        sizes[f] = sizes.get(f, 0) + 1
    # how far back a soul can actually see, as a fraction of its own life. Measured from
    # the WORLD TICK -- the first version subtracted created_tick from the SOUL'S AGE, which
    # are different clocks, and produced negative horizons.
    horizon = st.fmean(
        [(w.tick - min((m.created_tick for m in a.memory.items), default=w.tick)) /
         max(1, a.lifespan) for a in ags])
    return {"ticks": ticks, "alive": len(ags), "items": items, "warm": warm,
            "legend": carriers, "legend_pct": 100.0 * carriers / len(ags),
            "blocs": len(sizes), "biggest": max(sizes.values()) if sizes else 0,
            "horizon": horizon}


def main() -> None:
    print(f"  {N} souls, seed {SEED}, {LIVES} lifespans per arm, lore on\n")
    print(f"  {'scale':<7}{'lifespan':>9}{'ticks':>8}{'alive':>7}{'items':>8}{'warm':>7}"
          f"{'legend':>9}{'blocs':>7}{'biggest':>9}{'horizon':>9}")
    rows = {}
    for label, span in SCALES:
        r = run_scale(span)
        rows[label] = r
        print(f"  {label:<7}{span:>9}{r['ticks']:>8}{r['alive']:>7}{r['items']:>8.1f}"
              f"{r['warm']:>7.1f}{r['legend_pct']:>8.0f}%{r['blocs']:>7}{r['biggest']:>9}"
              f"{r['horizon']:>8.1%}")
    a, g = rows["arena"], rows["game"]
    t1 = g["items"] >= 0.5 * a["items"]
    t2 = g["warm"] >= 0.5 * a["warm"]
    t3 = g["legend_pct"] >= 50.0
    t4 = 1 < g["blocs"] < g["alive"]
    print(f"\n  T1 A SOUL STILL HAS A PAST     : {'PASS' if t1 else 'FAIL'}"
          f"   ({g['items']:.1f} items vs the arena's {a['items']:.1f})")
    print(f"  T2 BONDS SURVIVE THEIR MEMORIES: {'PASS' if t2 else 'FAIL'}"
          f"   ({g['warm']:.1f} warm vs {a['warm']:.1f})")
    print(f"  T3 A LEGEND OUTLIVES ITS TELLERS: {'PASS' if t3 else 'FAIL'}"
          f"   ({g['legend_pct']:.0f}% still carry it, vs {a['legend_pct']:.0f}%)")
    print(f"  T4 FACTIONS STILL FORM (control): {'PASS' if t4 else 'FAIL'}"
          f"   ({g['blocs']} blocs, biggest {g['biggest']} of {g['alive']})")
    ok = t1 and t2 and t3 and t4
    print(f"\n  VERDICT: {'THE SUBSTRATE SURVIVES GAME TIME' if ok else 'it does NOT -- see which claim fell'}")


if __name__ == "__main__":
    main()
