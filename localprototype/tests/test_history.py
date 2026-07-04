"""Tests for the Phase-0 recorders (scripts/history.py).

Pinned: town_line captures position/mood/bonds compactly and roundtrips through the
jsonl file; append_line rotates at the cap and never raises; pen_page_stats reduces a
day's raw motion to honest numbers (empty days included); torn final lines are skipped
on load. Recorders are read-only: building a line must not touch the world."""

import json

from agent.agent import Agent
from agent.bond import Bond
from scripts import history
from services.llm import MockLLM
from world.sim import World


def _town():
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    for i in range(3):
        a = Agent(f"s{i}", f"F{i}", (i * 10.0, 5.0), "You are a soul.", ["the well"],
                  w.llm, seed=i, temperament=0.0, lifespan=10 ** 6)
        a.bond_enabled = True
        w.add(a)
    w.agents[0].bonds["s1"] = Bond(trust=0.6, history=1.0)
    return w


def test_town_line_roundtrips(tmp_path):
    w = _town()
    with w.lock:
        line = history.town_line(w)
    path = str(tmp_path / "town_history.jsonl")
    history.append_line(path, line)
    back = history.load_jsonl(path)
    assert len(back) == 1
    sid, x, y, mood, bonds = back[0]["souls"][0]
    assert (sid, x, y) == ("s0", 0.0, 5.0)
    assert bonds == [["s1", 0.6]]
    assert isinstance(mood, float)


def test_append_rotates_and_load_skips_torn_lines(tmp_path):
    path = str(tmp_path / "h.jsonl")
    history.append_line(path, {"a": 1}, cap=5)      # tiny cap: next append rotates
    history.append_line(path, {"a": 2}, cap=5)
    assert (tmp_path / "h.jsonl.1").exists()
    with open(path, "a") as f:
        f.write('{"torn": ')                        # a crash mid-write
    assert [d["a"] for d in history.load_jsonl(path)] == [2]


def test_pen_page_stats_reduces_a_day_to_numbers():
    trace = [(0.1, 2.0, 0.4), (-0.3, 4.0, 0.6)]
    st = history.pen_page_stats(7, "harvest", trace, lifts=1)
    assert st["n"] == 2 and st["mean_speed"] == 3.0 and st["mean_abs_turn"] == 0.2
    assert history.pen_page_stats(8, "winter", [], 0)["n"] == 0   # a still day is a row too
