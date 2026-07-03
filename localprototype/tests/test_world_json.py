"""Fidelity proof for the JSON world snapshot (world/serialize.py).

Pickle's replacement is held to a harder standard than pickle ever was:
  - FIXPOINT: decode(encode(town)) must re-encode byte-identical -- nothing carried
    approximately, nothing quietly dropped.
  - IDENTICAL CONTINUATION: two towns restored from the same snapshot must live the SAME
    future (RNG state included) -- if a single field were lost, deterministic trajectories
    would diverge and this test would see it.
  - LOUD REFUSAL: an unencodable attribute names its exact path; a class outside the
    allowlist is refused at decode; a wrong format version is refused. Never a silently
    thinner town (the frozen-world lesson, §5.18).
"""


import pytest


from services.llm import MockLLM
from world.serialize import (WorldSnapshotError, world_from_json, world_to_json)


def _town(ticks=30):
    from santana_app.run import build_world
    llm = MockLLM(seed=7)
    w = build_world(llm, fast_wheel=True)
    for _ in range(ticks):
        with w.lock:
            w.step(speak=True)
    return w, llm


def test_snapshot_is_a_fixpoint():
    w, llm = _town()
    j1 = world_to_json(w)
    w2 = world_from_json(j1, llm)
    j2 = world_to_json(w2)
    assert j1 == j2, "decode(encode(town)) must re-encode byte-identical"


def test_restored_towns_live_the_same_future():
    w, llm = _town()
    j = world_to_json(w)
    a = world_from_json(j, MockLLM(seed=7))
    b = world_from_json(j, MockLLM(seed=7))
    for _ in range(40):
        with a.lock:
            a.step(speak=True)
        with b.lock:
            b.step(speak=True)
    assert a.tick == b.tick
    assert [(x.id, x.name, len(x.memory.items), round(x.memory.mood(), 9))
            for x in a.agents] == \
           [(x.id, x.name, len(x.memory.items), round(x.memory.mood(), 9))
            for x in b.agents], "one lost field diverges a deterministic trajectory"
    assert a.spoken == b.spoken


def test_the_llm_is_reinjected_never_carried():
    w, llm = _town(ticks=5)
    j = world_to_json(w)
    assert "MockLLM" not in j                      # the voice is not part of the town
    fresh = MockLLM(seed=99)
    w2 = world_from_json(j, fresh)
    assert w2.llm is fresh
    assert all(x.llm is fresh for x in w2.agents)


def test_unencodable_attribute_is_refused_with_its_path():
    w, _ = _town(ticks=1)
    w.agents[0].saboteur = lambda: None            # not snapshot material
    with pytest.raises(WorldSnapshotError) as exc:
        world_to_json(w)
    assert "saboteur" in str(exc.value)            # the exact attribute, named


def test_foreign_class_is_refused_at_decode():
    w, llm = _town(ticks=1)
    j = world_to_json(w).replace("world.sim:World", "os:system", 1)
    with pytest.raises(WorldSnapshotError):
        world_from_json(j, llm)


def test_wrong_format_version_is_refused():
    w, llm = _town(ticks=1)
    j = world_to_json(w).replace('{"format":1', '{"format":99', 1)
    with pytest.raises(WorldSnapshotError):
        world_from_json(j, llm)
