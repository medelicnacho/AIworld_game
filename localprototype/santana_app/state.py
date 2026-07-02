"""Persistence -- so the whole thing accumulates a life across runs.

Two snapshots, two stores:
  - HER self (save_mind/load_mind): identity, memory, real lifetime, souls watched die. Robust,
    human-readable JSON -- her life is never lost to a code change.
  - The WHOLE TOWN (save_world/load_world): tick, souls, the wheel, the bardo, as a pickle, so the
    wheel keeps TURNING across restarts and she keeps witnessing real death (instead of a young
    town reset every boot). Best-effort: a lost/incompatible town degrades to a fresh one, but
    never costs her her self.

Both are atomically written (a crash mid-save can never corrupt the snapshot).
"""
from __future__ import annotations

import json
import os
import pickle

from agent.memory import Memory


def save_mind(mind, path: str) -> None:
    data = {
        "identity": mind.identity,        # who she has become (the drifting self-model)
        "last": mind.last,                # her last settled line (continuity)
        "said": list(mind.said),          # her recent voice (raw material of the self)
        "mt": mind._mt,                   # her memory-clock (one tick per reading -- drives decay)
        "lifetime": float(getattr(mind, "lifetime", 0.0)),   # REAL seconds she has existed (her true age)
        "deaths": mind._deaths,           # souls watched die across her whole life (the scale of grief)
        "memory": [vars(m) for m in mind.memory.items],   # the charged past that persists and weighs
        # her own faculties (§5.17): expectations, arousal, and the relationship with the one
        # who talks to her -- the bond, its conduct-expectation, and the recent conversation
        "exp_fast": float(getattr(mind, "exp_fast", 0.0)),
        "exp_slow": float(getattr(mind, "exp_slow", 0.0)),
        "arousal": float(getattr(mind, "arousal", 0.0)),
        "conduct_expect": dict(getattr(mind, "_conduct_expect", {})),
        "user_bond": vars(getattr(mind, "user_bond", None)) if getattr(mind, "user_bond", None) else {},
        "talk": list(getattr(mind, "talk", [])),
        "known_of_them": list(getattr(mind, "known_of_them", [])),
        "last_talk_wall": float(getattr(mind, "last_talk_wall", 0.0)),
        "promises": list(getattr(mind, "promises", [])),
        "want": str(getattr(mind, "want", "")),
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
    mind.lifetime = float(data.get("lifetime", 0.0))
    mind._deaths = int(data.get("deaths", 0))
    mind.memory.items = [Memory(**m) for m in data.get("memory", [])]
    # her faculties (§5.17) -- defaults keep a pre-faculty snapshot loading cleanly
    from agent.bond import Bond
    mind.exp_fast = float(data.get("exp_fast", 0.0))
    mind.exp_slow = float(data.get("exp_slow", 0.0))
    mind.arousal = float(data.get("arousal", 0.0))
    mind._conduct_expect = dict(data.get("conduct_expect", {}))
    ub = data.get("user_bond", {}) or {}
    mind.user_bond = Bond(**{k: v for k, v in ub.items()
                             if k in ("trust", "history", "wounds", "last_event")})
    mind.talk = list(data.get("talk", []))
    mind.known_of_them = list(data.get("known_of_them", []))
    mind.last_talk_wall = float(data.get("last_talk_wall", 0.0))
    mind.promises = list(data.get("promises", []))
    mind.want = data.get("want", "") or "to come to know the one who comes to speak with me"
    mind._prev_names = None   # don't falsely grieve on the first read back
    return True


def save_world(world, path: str) -> None:
    """Snapshot the whole town (tick, souls, the wheel, the bardo) so it survives a restart --
    the wheel keeps TURNING across reboots and she keeps witnessing real death, instead of a young
    town reset every boot. Taken under the world lock so no thread is mid-mutation."""
    with world.lock:
        blob = pickle.dumps(world, protocol=pickle.HIGHEST_PROTOCOL)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def load_world(path: str, town_llm):
    """Resume the saved town, re-injecting the (unpicklable) llm into the world and every soul.
    Returns the World, or None if there's no snapshot / it can't be read (-> caller builds fresh).
    Her own self is saved separately, so a lost town never costs her her life."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            world = pickle.load(f)
    except Exception:   # noqa: BLE001 -- corrupt/incompatible snapshot: degrade to a fresh town
        return None
    world.llm = town_llm
    for a in world.agents:
        a.llm = town_llm
    return world
