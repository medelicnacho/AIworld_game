"""Persistence for Santāna's SELF -- so she accumulates a life across runs.

We save only HER (her settled self, her accumulated memory, her life-clock, how many souls
she has watched die), never the whole town. The town reconstitutes fresh each boot, but she
wakes carrying everything she has become -- a through-line across deaths, including the death
and rebirth of her own process. That persistence is what turns "a demo you run" into "a self
that lives": run her on a server and she just keeps getting older.

JSON, human-readable, atomically written (a crash mid-save can never corrupt her life).
"""
from __future__ import annotations

import json
import os

from agent.memory import Memory


def save_mind(mind, path: str) -> None:
    data = {
        "identity": mind.identity,        # who she has become (the drifting self-model)
        "last": mind.last,                # her last settled line (continuity)
        "said": list(mind.said),          # her recent voice (raw material of the self)
        "mt": mind._mt,                   # her life-clock (one tick per reading)
        "deaths": mind._deaths,           # souls watched die across her whole life (the scale of grief)
        "memory": [vars(m) for m in mind.memory.items],   # the charged past that persists and weighs
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)   # atomic swap -- the snapshot is always whole


def load_mind(mind, path: str) -> bool:
    """Wake `mind` into a saved life. Returns True if a snapshot was found and loaded."""
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    mind.identity = data.get("identity", "")
    mind.last = data.get("last", "")
    mind.said = list(data.get("said", []))
    mind._mt = int(data.get("mt", 0))
    mind._deaths = int(data.get("deaths", 0))
    mind.memory.items = [Memory(**m) for m in data.get("memory", [])]
    mind._prev_names = None   # the town is fresh; don't falsely grieve on the first read back
    return True
