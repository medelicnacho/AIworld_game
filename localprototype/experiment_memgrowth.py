"""MEMORY GROWS WITHOUT BOUND AT GAME SPANS -- and NOT from the floored-wound ratchet.

experiment_gamespan found memory/soul rising 11.6x at game lifespans and a 40-soul shard at
2.5x its 10Hz frame budget. The open question was WHICH memory: if it were the floored-wound
ratchet (experiment_forgiveness), then forgiveness would be the fix and a Stage 3 blocker.

It is not. Sampling composition through a game-span run (35000 lifespan), the un-prunable
FLOORED fraction is 0.0% at every tick. This is ORDINARY memory, and it does not plateau:

    tick  souls  items/soul   (stable ~44-soul founding cohort)
    1500     45        93.1
    3000     44       223.3      +130
    4500     44       376.5      +153
    6000     44       530.3      +154

Linear, no equilibrium. It SHOULD plateau: decay 0.995 + prune at 0.08 gives a memory a
~402-tick life, so items should settle at writes/tick x 402. They do not, which points at
REINFORCEMENT rather than fresh writes: write() merges a similar line and adds REINFORCE_BUMP
0.35, and a memory re-touched every ~90 ticks gains more than decay removes. In a town where
souls repeat their themes, a memory becomes permanent through reinforcement -- a SECOND
un-prunable class, unrelated to salience_floor. (Hypothesis, named for whoever tunes it; the
MEASURED fact is 0% floored and linear growth.)

The 457.9 endpoint in experiment_gamespan was DILUTED BY POPULATION GROWTH (births reset the
mean -- see the drop at tick 7500). A long-lived cohort at ~100 items/1000 ticks projects to
~3500 items/soul over a full 35000-tick life: a 40-soul shard at ~1960 ms/tick, ~20x the
100ms budget, not 2.5x.

CONSEQUENCES, recorded:
  * forgiveness is NOT this fix. It bounds the floored ratchet, which is real but separate,
    and its 7/10 stays a lab-scale problem, not a Stage 3 gate.
  * the shard budget needs a WORKING-SET bound -- a cap on items per soul, or decay scaled
    to lifespan so the ~402-tick horizon grows with the life. Different work; now the top
    item for gameworld Stage 3a.
  * the cost guard STAGES.md §3a plans must gate on ITEMS PER SOUL OVER TIME, not a town
    total -- the total hid this behind population growth for a full 42000-tick run.

  python3 -u experiment_memgrowth.py        # ~15 min; prints unbuffered, do not pipe to tail
"""
from __future__ import annotations

from scripts.arena_harness import build, run

LIFESPAN = 35000
TICKS = 12000
EVERY = 1500


def main() -> None:
    w = build(seed=11, founders=14)
    for a in w.agents:
        old = max(1, a.lifespan)
        a.age = int(a.age * LIFESPAN / old)
        a.lifespan = LIFESPAN
    print(f"  game lifespans ({LIFESPAN}), floored fraction sampled as it goes\n")
    print(f"  {'tick':>6}{'souls':>7}{'items/soul':>12}{'floored/soul':>14}"
          f"{'% un-prunable':>15}")

    def sample(t, world):
        tot = fl = 0
        for a in world.agents:
            for m in a.memory.items:
                tot += 1
                if getattr(m, "salience_floor", 0.0) > 0.0:
                    fl += 1
        n = len(world.agents) or 1
        print(f"  {t:>6}{n:>7}{tot / n:>12.1f}{fl / n:>14.1f}"
              f"{100 * fl / max(tot, 1):>14.1f}%", flush=True)

    run(w, TICKS, on_sample=sample, every=EVERY)
    print("\n  -> floored stays ~0%: the growth is ORDINARY memory, not the ratchet.")
    print("     forgiveness does not fix this; a working-set bound does.")


if __name__ == "__main__":
    main()
