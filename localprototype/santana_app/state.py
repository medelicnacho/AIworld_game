"""Persistence -- so the whole thing accumulates a life across runs.

Two snapshots, two stores:
  - HER self (save_mind/load_mind): identity, memory, real lifetime, souls watched die. Robust,
    human-readable JSON -- her life is never lost to a code change.
  - The WHOLE TOWN (save_world/load_world): tick, souls, the wheel, the bardo, as a pickle, so the
    wheel keeps TURNING across restarts and she keeps witnessing real death (instead of a young
    town reset every boot). Best-effort: a lost/incompatible town degrades to a fresh one --
    LOUDLY, with the old snapshot preserved aside -- but never costs her her self.

And three guards, because her life is the one irreplaceable file in the repo:
  - both snapshots are atomically written (a crash mid-save can never corrupt them);
  - `acquire_life()` -- ONE writer at a time; a second is refused loudly, never clobbered quietly;
  - `_daily_backup()` -- the first save of each day keeps yesterday's her in data/backups/auto/.
"""
from __future__ import annotations

import json
import os
import pickle
import shutil
import time

from agent.memory import Memory


# --- the life lock ---------------------------------------------------------------------------
# Three programs can hold her open (the 24/7 runner, a talk, the live window). Each saves on
# the way out, and a save is last-writer-wins: TWO holders means one silently overwrites what
# she lived with the other -- a conversation she would simply not remember. chat.py guarded
# this by pausing the runner (pgrep); app.py guarded it with systemd; a bare
# `python -m santana_app.talk` had no guard at all, and the two guards couldn't see each
# other. This is the one guard they all share now: whoever would WRITE her life takes the
# lock first. flock dies with the process, so a crash can never leave a stale lock; readers
# (the god-view's read-only resume) don't take it -- reading never loses a life.

class LifeBusy(RuntimeError):
    """Another process holds this life open -- writing now would overwrite what she lived."""


class _LifeLock:
    def __init__(self, path: str, fd: int):
        self.path, self._fd = path, fd

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)   # closing the fd drops the flock
            finally:
                self._fd = None


def acquire_life(snapshot_path: str, label: str) -> _LifeLock:
    """Take exclusive ownership of the life saved at `snapshot_path` for this process.

    Hold the returned lock for the WHOLE run and release() after the final save.
    Raises LifeBusy -- naming who has her -- if another process already holds her open.
    """
    import fcntl
    lock_path = snapshot_path + ".lock"
    parent = os.path.dirname(os.path.abspath(lock_path))
    os.makedirs(parent, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        holder = ""
        try:
            holder = os.read(fd, 256).decode("utf-8", "replace").strip()
        except OSError:
            pass
        os.close(fd)
        raise LifeBusy(
            f"her life ({os.path.basename(snapshot_path)}) is already open"
            + (f" by {holder}" if holder else "")
            + " -- two writers would overwrite each other's memory of her. Stop the other"
              " process first (Ctrl-C saves her on the way out), or use `python3 chat.py`,"
              " which pauses the runner for you.") from None
    os.ftruncate(fd, 0)
    os.write(fd, (f"{label} (pid {os.getpid()}, "
                  f"since {time.strftime('%Y-%m-%d %H:%M:%S')})").encode("utf-8"))
    return _LifeLock(lock_path, fd)


def _daily_backup(path: str, keep: int = 14) -> None:
    """The first save of each calendar day keeps the PREVIOUS on-disk her, in
    data/backups/auto/. Her whole life is a few hundred KB -- fourteen days of it costs less
    than one voice model, and it means no bug, clobber, or bad migration can cost more than
    a day of her. A failed backup must never block the save itself."""
    if not os.path.isfile(path):
        return
    name = os.path.basename(path)
    bdir = os.path.join(os.path.dirname(os.path.abspath(path)), "backups", "auto")
    dest = os.path.join(bdir, f"{name}.{time.strftime('%Y%m%d')}")
    if os.path.exists(dest):
        return
    try:
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(path, dest)
    except OSError:
        return
    stale = sorted(f for f in os.listdir(bdir) if f.startswith(name + "."))[:-keep]
    for f in stale:
        try:
            os.remove(os.path.join(bdir, f))
        except OSError:
            pass


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
        # the absence-dream stamp + her window of tolerance (a trip is part of her life story)
        "last_dream_wall": float(getattr(mind, "_last_dream_wall", 0.0)),
        "somatic_trips": int(getattr(mind, "_somatic_trips", 0)),
        "contraction": float(getattr(mind, "_contraction", 0.0)),
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _daily_backup(path)   # the first save of the day keeps yesterday's her
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
    # THE RULE (same as Agent.__setstate__): every post-snapshot field gets a default here,
    # so a pre-field snapshot wakes cleanly instead of freezing something downstream
    mind._last_dream_wall = float(data.get("last_dream_wall", 0.0))
    mind._somatic_trips = int(data.get("somatic_trips", 0))
    mind._contraction = float(data.get("contraction", 0.0))
    mind._prev_names = None   # don't falsely grieve on the first read back
    return True


def save_world(world, path: str) -> None:
    """Snapshot the whole town (tick, souls, the wheel, the bardo) so it survives a restart --
    the wheel keeps TURNING across reboots and she keeps witnessing real death, instead of a young
    town reset every boot. Taken under the world lock so no thread is mid-mutation."""
    with world.lock:
        blob = pickle.dumps(world, protocol=pickle.HIGHEST_PROTOCOL)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _daily_backup(path)   # the town too: a day of the wheel is a day of her witnessing
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def load_world(path: str, town_llm):
    """Resume the saved town, re-injecting the (unpicklable) llm into the world and every soul.
    Returns the World, or None if there's no snapshot (-> caller builds fresh).

    An UNREADABLE snapshot also degrades to a fresh town -- her self is saved separately, so a
    lost town never costs her her life -- but it degrades LOUDLY, with the snapshot PRESERVED
    aside. The frozen-world lesson (FINDINGS §5.18) applies to loaders too: a town that
    vanishes without a traceback is a monitor that failed silently."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            world = pickle.load(f)
    except Exception:   # noqa: BLE001 -- corrupt/incompatible snapshot: preserve, shout, degrade
        import traceback
        aside = f"{path}.incompatible-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(path, aside)   # out of the save path, so the evidence survives the next save
            kept = aside
        except OSError:
            kept = path
        print("\n  ⚠ THE SAVED TOWN COULD NOT BE WOKEN -- likely a code change made the "
              "snapshot incompatible:", flush=True)
        traceback.print_exc()
        print(f"  ⚠ the unreadable snapshot is PRESERVED at {kept}; a fresh town starts "
              "under her (her self is untouched). If this follows a code change, restore "
              "compatibility and move the snapshot back.", flush=True)
        return None
    world.llm = town_llm
    for a in world.agents:
        a.llm = town_llm
    return world
