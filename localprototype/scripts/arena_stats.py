"""scripts/arena_stats.py -- the population-genetics read on a living arena.

EVOLUTION_NEXT stage 1. The arena's whole thesis is that bloodlines DIVERGE under
pressure, and until now the only way to check was to hand-write a throwaway script --
which is how the arena ran for a full founder turnover with its selection engine
switched off and nobody watching (the stage-0 find: genome means still sitting at the
founding ~0.5 while sd had grown to 0.11-0.22 -- heredity working, selection not biting).

The unit that matters is the TRAJECTORY, not the snapshot. A single sample cannot tell
"the mean is 0.45" from "the mean is 0.45 and falling" -- the second is a selective
sweep and the first is nothing. So this appends one JSONL row per sample and the rows
are the finding.

Reads the SAVED SNAPSHOT (data/<arena>/town.json), not the /bridge/state HTTP feed,
for two reasons: the bridge rounds to 2dp (quantising the ~0.02-0.05 drifts this exists
to detect) and carries only 4 of the 7 germ-line dials. The live arenas autosave every
90s, so a snapshot read is a live read one autosave behind.

    # one read of a live arena, printed
    python3 scripts/arena_stats.py --world data/evolution/town.json

    # follow it: a row every 5 min, appended, until ctrl-C
    python3 scripts/arena_stats.py --world data/evolution/town.json --watch 300

    # compare the two regimes as they stand
    python3 scripts/arena_stats.py --compare data/evolution/town.json data/evolution_press/town.json

    # from a headless run (stage 3), on a live World object:
    from scripts.arena_stats import genome_stats
    row = genome_stats(world.agents)

Error bars come from the house instrument (scripts/stats.py summary(), M1), so a mean
here carries the same refusal-where-none-exists discipline as every other verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.genome import DIALS                       # noqa: E402
from scripts.stats import summary                    # noqa: E402

# --- the founding baseline, MEASURED not assumed -----------------------------------------
# "Has this dial moved?" needs a baseline, and the obvious guess -- 0.5 for every [0,1]
# dial -- is WRONG for most of them: grip founds on uniform(0.2,0.5) and compassion on a
# flat 0.6 (genesis.endow_faculties), openness on uniform(0.25,0.55) and wrath on
# uniform(0.3,0.7) (genome.from_agent), metabolism/boldness/temperament on their own
# ranges (evolution._found_souls). Assuming 0.5 reported grip as -0.142 drifted and
# openness as -0.112 when both had in truth moved ~0.01 -- a fabricated selective sweep.
#
# Those centres live in three files and would rot if copied here, so they are not copied:
# this founds a throwaway population through the REAL code path and measures it. It cannot
# disagree with the founding code because it IS the founding code.
_CENTRE_CACHE: dict = {}


def founding_centre(n: int = 600, seed: int = 0) -> dict:
    """Per-dial mean of a freshly founded population -- the baseline `drift` is measured
    against. Cached per process; ~a second for 600 souls."""
    if _CENTRE_CACHE:
        return _CENTRE_CACHE
    import random
    from santana_app.evolution import _found_souls
    from services.llm import MockLLM
    from world.sim import World
    w = World(rebirth_enabled=False, events_enabled=False)
    w.llm = MockLLM(seed=seed)
    _found_souls(w, random.Random(seed), n)
    for d in DIALS:
        xs = [getattr(a.genome, d) for a in w.agents
              if getattr(a, "genome", None) is not None
              and isinstance(getattr(a.genome, d, None), (int, float))]
        if xs:
            _CENTRE_CACHE[d] = statistics.fmean(xs)
    return _CENTRE_CACHE


def genome_stats(agents, centre: dict | None = None) -> dict:
    """The population read: one row. Works on a live World's agents or a restored
    snapshot's -- stage 3's headless batch imports this rather than reinventing it.

    `centre` is the founding baseline drift is measured against; None measures it once
    through the real founding path (founding_centre). Pass {} to omit drift entirely."""
    centre = founding_centre() if centre is None else centre
    alive = list(agents)
    genomes = [a.genome for a in alive if getattr(a, "genome", None) is not None]
    row: dict = {
        "n": len(alive),
        "n_genomes": len(genomes),
        "castes": {},
        "factions": {},
        "dials": {},
    }
    for a in alive:
        c = getattr(a, "caste", "warrior")
        row["castes"][c] = row["castes"].get(c, 0) + 1
    # blocs as the town's own affinity partition sees them (the same read the cockpit
    # rings draw), not any assigned label -- emergence discipline, §5.6
    try:
        from services.factions import partition
        for f in partition(alive).values():       # id -> bloc index
            row["factions"][str(f)] = row["factions"].get(str(f), 0) + 1
    except Exception:   # noqa: BLE001 -- a faction read must never break the instrument
        row["factions"] = {}
    for d in DIALS:
        xs = [getattr(g, d) for g in genomes if isinstance(getattr(g, d, None), (int, float))]
        if not xs:
            continue
        s = summary(xs)
        row["dials"][d] = {
            "mean": round(s.mean, 4),
            "sd": round(s.sd, 4) if s.sd is not None else None,
            "min": round(min(xs), 4),
            "max": round(max(xs), 4),
        }
        # how far the population has walked from its FOUNDING centre. THIS is the
        # selection signal: sd growing with mean still at centre = heredity working
        # and selection idle (the stage-0 diagnosis, in one number).
        if d in centre:
            row["dials"][d]["drift"] = round(s.mean - centre[d], 4)
    return row


def read_snapshot(path: str) -> dict:
    """One row from a saved town. Restores through the real deserializer (the tagged
    JSON is not meant to be hand-parsed) with a mock voice -- nothing here speaks."""
    from services.llm import MockLLM
    from world.serialize import world_from_json
    with open(path, encoding="utf-8") as f:
        w = world_from_json(f.read(), MockLLM(seed=0))
    row = genome_stats(w.agents)
    row["tick"] = getattr(w, "tick", None)
    row["path"] = path
    row["t"] = time.time()
    return row


def _fmt(row: dict) -> str:
    out = [f"  tick {row.get('tick')}   souls {row['n']}   "
           f"castes {dict(sorted(row['castes'].items()))}"]
    facs = sorted(row["factions"].items(), key=lambda kv: -kv[1])[:5]
    if facs:
        out.append(f"  blocs (top 5): {dict(facs)}   [{len(row['factions'])} total]")
    out.append(f"  {'dial':<13}{'mean':>9}{'drift':>9}{'sd':>8}{'min':>8}{'max':>8}")
    for d, v in row["dials"].items():
        sd = f"{v['sd']:.3f}" if v["sd"] is not None else "  n=1"
        dr = f"{v['drift']:+9.3f}" if "drift" in v else f"{'-':>9}"
        out.append(f"  {d:<13}{v['mean']:>+9.3f}{dr}{sd:>8}"
                   f"{v['min']:>+8.2f}{v['max']:>+8.2f}")
    return "\n".join(out)


def _compare(paths: list[str]) -> None:
    rows = []
    for p in paths:
        if not os.path.isfile(p):
            print(f"  (no snapshot at {p} -- has that arena saved yet?)")
            continue
        rows.append(read_snapshot(p))
    if len(rows) < 2:
        return
    names = [os.path.basename(os.path.dirname(r["path"])) or r["path"] for r in rows]
    print(f"\n  {'dial':<13}" + "".join(f"{n:>16}" for n in names) + f"{'Δ':>10}")
    for d in DIALS:
        if not all(d in r["dials"] for r in rows):
            continue
        means = [r["dials"][d]["mean"] for r in rows]
        cells = "".join(f"{m:>+16.3f}" for m in means)
        print(f"  {d:<13}{cells}{means[-1] - means[0]:>+10.3f}")
    print("\n  NB a difference here is a SCOUTING read: two live worlds are n=1 per arm.")
    print("  The powered verdict needs the seeded batch (M3: d~0.45 -> ~40 seeds).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--world", default="data/evolution/town.json",
                   help="the arena snapshot to read (default: the watch arena)")
    p.add_argument("--watch", type=float, default=0.0, metavar="SECS",
                   help="follow: re-read every SECS and append a row (0 = one read)")
    p.add_argument("--out", default=None,
                   help="append JSONL here (default: <arena dir>/genome_log.jsonl)")
    p.add_argument("--compare", nargs="+", metavar="SNAPSHOT",
                   help="print two or more arenas' dial means side by side, and stop")
    args = p.parse_args()

    if args.compare:
        _compare(args.compare)
        return
    if not os.path.isfile(args.world):
        print(f"  no snapshot at {args.world}\n  (a live arena writes one on its "
              f"autosave -- give it ~90s, or stop it cleanly with ctrl-C)")
        raise SystemExit(1)
    out = args.out or os.path.join(os.path.dirname(args.world), "genome_log.jsonl")

    # a snapshot only changes when the arena autosaves (~90s), so a faster poll would
    # log the same tick repeatedly -- duplicate rows are not a flat trajectory, they
    # are a flat INSTRUMENT, and telling those apart later is exactly the confusion
    # this whole stage exists to remove. One row per distinct tick.
    last_tick = None
    while True:
        row = read_snapshot(args.world)
        fresh = row.get("tick") != last_tick
        if fresh:
            last_tick = row.get("tick")
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        print(_fmt(row), flush=True)
        if args.watch <= 0:
            print(f"\n  appended 1 row -> {out}")
            return
        note = f"appended -> {out}" if fresh else "same tick as last row -- not logged"
        print(f"  ... {note}; next read in {args.watch:.0f}s\n", flush=True)
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
