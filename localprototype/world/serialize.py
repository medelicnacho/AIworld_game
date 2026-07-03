"""Portable world snapshots: the whole town as versioned, tagged JSON.

The town used to persist as a PICKLE (santana_app/state.py) -- full fidelity, zero
portability: a binary only this Python can read, unreadable in a diff, and the #1 hazard
for the game-engine port (ROADMAP Track G), whose engine must be able to open a town.
This module is pickle's replacement: the same reflective fidelity (it walks
__getstate__/__dict__ exactly as pickle does, so NEW FIELDS ARE CARRIED AUTOMATICALLY --
no hand-kept schema to rot), written as tagged JSON a human can read and another language
can parse.

Fidelity is not asserted, it is TESTED (tests/test_world_json.py): a snapshot must be a
FIXPOINT (decode(encode(w)) re-encodes byte-identical) and a restored town must continue
IDENTICALLY (same RNG states -> same trajectory, tick for tick, as a second restore).

Failure is LOUD by design: an unencodable value raises WorldSnapshotError naming the
exact attribute path -- never a silently thinner town (the frozen-world lesson, §5.18).

Tags (a "~" prefix on a single-key dict): ~t tuple, ~s set, ~dq deque(+maxlen),
~dd defaultdict (factory from a fixed allowlist -- callables cannot ride in data),
~rng random.Random, ~d dict-with-nonstring-keys, ~o project object (allowlisted modules
only: agent.*, world.*, services.* -- a snapshot cannot smuggle in arbitrary classes).
"""
from __future__ import annotations

import importlib
import json
import random
from collections import defaultdict, deque

FORMAT_VERSION = 1
_ALLOWED_PREFIXES = ("agent", "world", "services")
_TAGS = ("~t", "~s", "~dq", "~dd", "~rng", "~d", "~o")
# defaultdict factories a snapshot may name: the safe primitives, nothing callable-in-data.
# (Caught by the identical-continuation test: a defaultdict decayed to plain dict restored
# a town whose Markov minds crashed on their first unseen word.)
_DD_FACTORIES = {"list": list, "dict": dict, "set": set, "int": int, "float": float}


class WorldSnapshotError(RuntimeError):
    """A value the snapshot cannot carry (or reconstruct) -- raised loudly, with its path."""


def _encode(o, path: str):
    if o is None or isinstance(o, (bool, int, str)):
        return o
    if isinstance(o, float):
        if o != o or o in (float("inf"), float("-inf")):
            raise WorldSnapshotError(f"non-finite float at {path}: {o!r}")
        return o
    if isinstance(o, list):
        return [_encode(v, f"{path}[{i}]") for i, v in enumerate(o)]
    if isinstance(o, tuple):
        return {"~t": [_encode(v, f"{path}[{i}]") for i, v in enumerate(o)]}
    if isinstance(o, set):
        return {"~s": sorted((_encode(v, f"{path}{{}}") for v in o),
                             key=lambda x: json.dumps(x, sort_keys=True))}
    if isinstance(o, deque):
        return {"~dq": [_encode(v, f"{path}[{i}]") for i, v in enumerate(o)],
                "maxlen": o.maxlen}
    if isinstance(o, random.Random):
        return {"~rng": _encode(o.getstate(), f"{path}.getstate()")}
    if isinstance(o, defaultdict):
        fname = getattr(o.default_factory, "__name__", None)
        if fname not in _DD_FACTORIES:
            raise WorldSnapshotError(f"defaultdict at {path} has factory "
                                     f"{o.default_factory!r} -- only "
                                     f"{sorted(_DD_FACTORIES)} can ride in a snapshot")
        return {"~dd": fname,
                "items": [[_encode(k, f"{path}<key>"), _encode(v, f"{path}[{k!r}]")]
                          for k, v in o.items()]}
    if isinstance(o, dict):
        if all(isinstance(k, str) and not k.startswith("~") for k in o):
            return {k: _encode(v, f"{path}.{k}") for k, v in o.items()}
        return {"~d": [[_encode(k, f"{path}<key>"), _encode(v, f"{path}[{k!r}]")]
                       for k, v in o.items()]}
    cls = type(o)
    if cls.__module__.split(".")[0] in _ALLOWED_PREFIXES:
        state = o.__getstate__() if hasattr(o, "__getstate__") else dict(o.__dict__)
        if not isinstance(state, dict):
            raise WorldSnapshotError(f"{cls.__name__}.__getstate__ at {path} is not a dict")
        return {"~o": f"{cls.__module__}:{cls.__qualname__}",
                "s": {k: _encode(v, f"{path}.{k}") for k, v in state.items()}}
    raise WorldSnapshotError(
        f"cannot carry {cls.__module__}.{cls.__qualname__} at {path} -- either it does not "
        f"belong in a snapshot (exclude it in __getstate__, like World.lock/llm) or "
        f"world/serialize.py needs a tag for it. Refusing to write a thinner town.")


def _decode(o, path: str):
    if isinstance(o, list):
        return [_decode(v, f"{path}[{i}]") for i, v in enumerate(o)]
    if not isinstance(o, dict):
        return o
    if "~t" in o:
        return tuple(_decode(v, f"{path}[t]") for v in o["~t"])
    if "~s" in o:
        return set(_decode(v, f"{path}[s]") for v in o["~s"])
    if "~dq" in o:
        return deque((_decode(v, f"{path}[dq]") for v in o["~dq"]), maxlen=o.get("maxlen"))
    if "~rng" in o:
        r = random.Random()
        r.setstate(_decode(o["~rng"], f"{path}.rng"))
        return r
    if "~dd" in o:
        if o["~dd"] not in _DD_FACTORIES:
            raise WorldSnapshotError(f"snapshot names a defaultdict factory outside the "
                                     f"allowlist at {path}: {o['~dd']!r}")
        d = defaultdict(_DD_FACTORIES[o["~dd"]])
        for k, v in o["items"]:
            d[_decode(k, f"{path}<key>")] = _decode(v, f"{path}[?]")
        return d
    if "~d" in o:
        return {_decode(k, f"{path}<key>"): _decode(v, f"{path}[?]") for k, v in o["~d"]}
    if "~o" in o:
        mod_name, _, qual = o["~o"].partition(":")
        if mod_name.split(".")[0] not in _ALLOWED_PREFIXES:
            raise WorldSnapshotError(f"snapshot names a class outside the allowlist at "
                                     f"{path}: {o['~o']}")
        try:
            cls = importlib.import_module(mod_name)
            for part in qual.split("."):
                cls = getattr(cls, part)
        except (ImportError, AttributeError) as exc:
            raise WorldSnapshotError(f"snapshot class {o['~o']} at {path} no longer exists "
                                     f"({exc}) -- a code change broke compatibility; fix it "
                                     f"or accept a fresh town") from exc
        obj = object.__new__(cls)
        state = {k: _decode(v, f"{path}.{k}") for k, v in o["s"].items()}
        if hasattr(obj, "__setstate__"):
            obj.__setstate__(state)      # the pickle rule holds: defaults for new fields
        else:
            obj.__dict__.update(state)
        return obj
    return {k: _decode(v, f"{path}.{k}") for k, v in o.items()}


def world_to_json(world) -> str:
    """The whole town -- tick, souls, the wheel, every faculty -- as one JSON document.
    Taken under the world lock so no thread is mid-mutation (same rule as the pickle had)."""
    with world.lock:
        doc = {"format": FORMAT_VERSION, "world": _encode(world, "world")}
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def world_from_json(text: str, town_llm):
    """Rebuild the town and re-inject the (never-serialized) llm into it and every soul."""
    doc = json.loads(text)
    fmt = doc.get("format")
    if fmt != FORMAT_VERSION:
        raise WorldSnapshotError(f"snapshot format {fmt!r}, this code reads {FORMAT_VERSION} "
                                 "-- migrate deliberately, not silently")
    world = _decode(doc["world"], "world")
    world.llm = town_llm
    for a in world.agents:
        a.llm = town_llm
    return world
