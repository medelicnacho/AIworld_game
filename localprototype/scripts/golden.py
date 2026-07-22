"""scripts/golden.py -- frozen trajectories the port must reproduce.

gameworld/PLAN.md M2's gate is "re-run the four keystones and reproduce the lab's verdicts",
and ROADMAP §2.2 calls the harness the port's ring test. A keystone that passes or fails at
the END of a run tells you THAT the port is wrong, not WHERE. A frozen trajectory tells you
the tick at which it diverged, and from which mechanism.

So: the Python lab becomes the ORACLE. Freeze a handful of seeded runs -- population,
positions, mood, bonds, memory, factions, sampled every N ticks -- as plain JSON. The TS
port replays the same seeds and diffs. First mismatching row names the mechanism.

The fingerprints are deliberately COARSE (sums and counts, rounded): a port is not required
to match float-for-float through a different language's math library, but it IS required to
keep the same souls alive, bonded and clustered at the same ticks. Anything finer would fail
on rounding and teach nothing; anything coarser would pass while the town was wrong.

    python3 scripts/golden.py --write     # regenerate (only when a change is INTENDED)
    python3 scripts/golden.py --check     # verify the current code still reproduces them
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.json")
SEEDS = (11, 12, 13)
FOUNDERS = 16
TICKS = 600
EVERY = 100


def fingerprint(w) -> dict:
    """One coarse, portable row. Sums and counts -- never float-exact positions."""
    from world.factions import factions_of
    ags = w.agents
    warm = sum(1 for a in ags for b in (getattr(a, "bonds", {}) or {}).values()
               if getattr(b, "trust", 0.0) > 0.15)
    facs = {f for f in factions_of(w).values() if f >= 0}
    return {
        "tick": w.tick,
        "souls": len(ags),
        "x": round(sum(a.position[0] for a in ags), 2),
        "y": round(sum(a.position[1] for a in ags), 2),
        "wellbeing": round(sum(a.wellbeing for a in ags), 4),
        "mood": round(sum(a.memory.mood() for a in ags), 4),
        "items": sum(len(a.memory.items) for a in ags),
        "warm_bonds": warm,
        "factions": len(facs),
    }


def trajectory(seed: int) -> list:
    from scripts.arena_harness import build, run
    rows: list = []
    w = build(seed=seed, founders=FOUNDERS)
    run(w, TICKS, on_sample=lambda t, world: rows.append(fingerprint(world)), every=EVERY)
    return rows


def generate() -> dict:
    return {"spec": {"seeds": list(SEEDS), "founders": FOUNDERS,
                     "ticks": TICKS, "every": EVERY},
            "runs": {str(s): trajectory(s) for s in SEEDS}}


def check() -> list:
    """Returns the mismatches -- empty means the current code still reproduces the lab."""
    with open(GOLDEN, encoding="utf-8") as f:
        want = json.load(f)
    bad = []
    for seed, rows in want["runs"].items():
        got = trajectory(int(seed))
        if len(got) != len(rows):
            bad.append(f"seed {seed}: {len(got)} rows, expected {len(rows)}")
            continue
        for g, r in zip(got, rows):
            for k, v in r.items():
                if g.get(k) != v:
                    bad.append(f"seed {seed} tick {r['tick']}: {k} = {g.get(k)}, "
                               f"expected {v}")
    return bad


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true",
                   help="regenerate the fixtures -- ONLY when a change is intended")
    p.add_argument("--check", action="store_true", help="verify current code matches")
    args = p.parse_args()
    if args.write:
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(generate(), f, indent=1)
        print(f"  wrote {GOLDEN}")
        print("  NB a diff here is a BEHAVIOUR CHANGE. Read it before committing it.")
        return
    bad = check()
    if not bad:
        print(f"  all {len(SEEDS)} trajectories reproduce exactly")
        return
    print(f"  {len(bad)} mismatches -- the FIRST names where it went wrong:")
    for line in bad[:8]:
        print(f"    {line}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
