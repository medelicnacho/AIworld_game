"""scripts/psyche_stats.py -- the read on a mind's stream of consciousness.

WORKSPACE_NEXT stage W0. `agent/workspace.py` keeps a 4000-entry log of who held the floor
each tick, and `experiment_psyche.py` reads it for verdicts -- but nothing reads it WHILE IT
RUNS. The four numbers that say whether a workspace is alive are all in that log and none of
them were watchable:

  floor-share   who the mind is, in proportion -- and whether one part has taken it over
  turnover      how often the floor changes hands. 0 = a frozen note, not a mind
  reign length  how long a moment lasts (hysteresis working, or flickering every tick)
  entropy       how spread the succession is. Read WITH turnover, never alone: churn with
                high entropy is noise, not a stream (the §5.13 lesson, in the mind's terms)

W2 will let a part read the workspace back, and the failure mode there is a self-reinforcing
loop that FREEZES the floor -- exactly what the §5.13 share-penalty formula was measured to
do before fatigue-with-memory replaced it. This exists so that freeze is caught the moment
it appears rather than after a verdict is built on it.

    # a live mind (run her with --psyche), or any saved snapshot
    python3 scripts/psyche_stats.py --world data/santana/town.json

    # follow it
    python3 scripts/psyche_stats.py --world data/santana/town.json --watch 120

    # from a headless run, on a live World:
    from scripts.psyche_stats import workspace_stats
    row = workspace_stats(world.psyche)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _runs(log: list) -> list:
    """The log as (name, length) reigns -- a moment is a RUN, not a tick."""
    out: list = []
    for name in log:
        if out and out[-1][0] == name:
            out[-1][1] += 1
        else:
            out.append([name, 1])
    return out


def workspace_stats(ws, window: int = 0) -> dict:
    """The four numbers, off a Workspace (or anything with .log/.names). `window` reads
    only the last N ticks -- the RECENT stream, for watching a change take hold."""
    log = list(getattr(ws, "log", []) or [])
    if window > 0:
        log = log[-window:]
    row: dict = {"ticks": len(log), "parts": 0, "turnovers": 0, "turnover_rate": None,
                 "mean_reign": None, "entropy": None, "share": {}, "reigning": None,
                 "fatigue": {}}
    if not log:
        return row
    counts: dict = {}
    for name in log:
        counts[name] = counts.get(name, 0) + 1
    row["parts"] = len(counts)
    row["share"] = {k: round(v / len(log), 4)
                    for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}
    runs = _runs(log)
    row["turnovers"] = max(0, len(runs) - 1)
    row["turnover_rate"] = round(row["turnovers"] / len(log), 4)
    row["mean_reign"] = round(statistics.fmean(r[1] for r in runs), 2)
    # Shannon entropy of the floor-share, in bits. Alone it says nothing (a frozen mind
    # and a noisy one differ by TURNOVER, not by spread) -- read the pair.
    row["entropy"] = round(-sum((c / len(log)) * math.log2(c / len(log))
                                for c in counts.values()), 4)
    row["max_entropy"] = round(math.log2(len(counts)), 4) if len(counts) > 1 else 0.0
    try:
        row["reigning"] = ws.reigning()
        row["fatigue"] = {ws.names.get(k, k): round(v, 3)
                          for k, v in sorted(getattr(ws, "f", {}).items(),
                                             key=lambda kv: -kv[1])}
    except Exception:   # noqa: BLE001 -- a live read must never break the instrument
        pass
    return row


def read_snapshot(path: str, window: int = 0) -> dict:
    from services.llm import MockLLM
    from world.serialize import world_from_json
    with open(path, encoding="utf-8") as f:
        w = world_from_json(f.read(), MockLLM(seed=0))
    ws = getattr(w, "psyche", None)
    if ws is None:
        raise SystemExit(f"  {path} has no psyche -- that world was not run with --psyche\n"
                         f"  (World.psyche defaults to None: the workspace is off unless asked)")
    row = workspace_stats(ws, window=window)
    row["tick"] = getattr(w, "tick", None)
    row["path"] = path
    row["t"] = time.time()
    return row


def _fmt(row: dict) -> str:
    if not row["ticks"]:
        return "  the log is empty -- has the workspace stepped yet?"
    out = [f"  tick {row.get('tick')}   stream {row['ticks']} ticks   "
           f"{row['parts']} parts   reigning now: {row['reigning']}"]
    ent = f"{row['entropy']:.2f}/{row.get('max_entropy', 0):.2f}"
    out.append(f"  turnovers {row['turnovers']}  (rate {row['turnover_rate']:.3f})   "
               f"mean reign {row['mean_reign']} ticks   entropy {ent} bits")
    if row["turnover_rate"] == 0.0:
        out.append("  ** FROZEN: the floor never changed hands. That is a stuck note, "
                   "not a stream -- check fatigue. **")
    out.append(f"  {'part':<12}{'floor share':>13}   {'fatigue':>8}")
    for name, sh in row["share"].items():
        fat = row["fatigue"].get(name)
        bar = "#" * int(round(sh * 30))
        out.append(f"  {name:<12}{sh:>12.1%}   "
                   f"{(f'{fat:.2f}' if fat is not None else '-'):>8}  {bar}")
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--world", required=True, help="a snapshot of a world run with --psyche")
    p.add_argument("--window", type=int, default=0,
                   help="read only the last N ticks of the stream (0 = all of it)")
    p.add_argument("--watch", type=float, default=0.0, metavar="SECS",
                   help="follow: re-read every SECS and append a row (0 = one read)")
    p.add_argument("--out", default=None, help="append JSONL here")
    args = p.parse_args()
    out = args.out or os.path.join(os.path.dirname(args.world), "psyche_log.jsonl")
    last = None
    while True:
        row = read_snapshot(args.world, window=args.window)
        fresh = row.get("tick") != last
        if fresh:                       # one row per distinct tick (the arena_stats lesson:
            last = row.get("tick")      # duplicate rows are a flat instrument, not a flat mind)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        print(_fmt(row), flush=True)
        if args.watch <= 0:
            print(f"\n  appended 1 row -> {out}")
            return
        note = f"appended -> {out}" if fresh else "same tick -- not logged"
        print(f"  ... {note}; next read in {args.watch:.0f}s\n", flush=True)
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
