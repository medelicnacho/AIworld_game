"""history.py -- the passive recorders' shared format (Phase 0 of the V-series).

The live towns' visible life -- who stood where, feeling what, bonded to whom; what her
pen did all day -- used to evaporate the moment it happened. These helpers write it down
so the visual-emergence studies (V1 emotional weather, V2 fellowships-take-territory,
V3 drawing motifs; pre-registered in RESEARCH.md) can be run OBSERVATIONALLY on the
towns' real lives, not only on lab reruns.

One JSON line per sample, append-only, size-capped with one prior epoch kept -- the
hand_history pattern. Everything here is read-only with respect to the world: a
recorder must never touch what it records."""
from __future__ import annotations

import json
import os

CAP_BYTES = 50_000_000     # ~months of town samples; one .1 epoch kept on rotation


def town_line(world) -> dict:
    """One sample of the town's visible life. CALL UNDER THE WORLD LOCK; the caller
    appends the returned dict outside it (snapshot-then-write, the house contract)."""
    from world import clock as _clock
    souls = []
    for a in world.agents:
        bonds = [[oid, round(b.trust, 2)] for oid, b in getattr(a, "bonds", {}).items()
                 if abs(b.trust) >= 0.10]
        souls.append([a.id, round(a.position[0], 1), round(a.position[1], 1),
                      round(a.felt_mood(), 3), bonds])
    return {"tick": world.tick,
            "season": (_clock.season(world.tick, world.day_ticks)
                       if world.clock_enabled else ""),
            "souls": souls}


def pen_page_stats(day: int, season: str, trace: list, lifts: int) -> dict:
    """One archived day-page of her pen, as numbers (V3 reads these, never the SVGs).
    trace: the day's accumulated (turn, speed, hue) tuples from Pen.last_trace."""
    n = len(trace)
    if n == 0:
        return {"day": day, "season": season, "n": 0, "mean_speed": 0.0,
                "mean_abs_turn": 0.0, "mean_hue": 0.5, "lifts": lifts}
    return {"day": day, "season": season, "n": n,
            "mean_speed": round(sum(t[1] for t in trace) / n, 3),
            "mean_abs_turn": round(sum(abs(t[0]) for t in trace) / n, 4),
            "mean_hue": round(sum(t[2] for t in trace) / n, 4),
            "lifts": lifts}


def append_line(path: str, obj: dict, cap: int = CAP_BYTES) -> None:
    """Append one JSON line; rotate to .1 at the cap. A failed write is a lost sample,
    never a crash (the recorder must not be able to hurt what it records)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > cap:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    except Exception:   # noqa: BLE001
        pass


def load_jsonl(path: str) -> list[dict]:
    """Read a recorder file (skipping any torn final line)."""
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out
