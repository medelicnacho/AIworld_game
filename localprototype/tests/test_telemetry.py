"""Tests for the telemetry recorder: the run must leave an analyzable trace.

A behavior experiment is only as good as its data recorder. These tests assert
the Recorder writes exactly one well-formed JSONL row per tick, that spoken lines
and fired events land in the right tick's row, and that the recorded mood moves
the way the perturbation should move it -- so a treatment run and its control can
be compared after the fact.

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_telemetry.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

# allow `python tests/test_telemetry.py` from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import Agent
from services.telemetry import Recorder
from world.events import EventBus, WorldEvent
from world.sim import World


class StubLLM:
    """Deterministic, no-network backend."""

    def speak(self, ctx):
        return "stub line"


def _agent(agent_id: str, seed: int, llm, temperament: float = 0.0) -> Agent:
    return Agent(agent_id, agent_id.upper(), (0.0, 0.0), "a persona",
                 ["a seed phrase"], llm, seed=seed, temperament=temperament)


def _run_and_read(events, ticks, enabled=True, run_id="t"):
    """Run a world with a Recorder, then return the parsed JSONL rows."""
    path = tempfile.mktemp(suffix=".jsonl")
    bus = EventBus()
    world = World(bus, events=events, events_enabled=enabled)
    world.add(_agent("a0", 1, StubLLM(), temperament=0.0))
    world.add(_agent("a1", 2, StubLLM(), temperament=0.0))
    rec = Recorder(path, world, run_id=run_id)
    try:
        with redirect_stderr(io.StringIO()):
            world.run(ticks)
    finally:
        rec.close()
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    os.unlink(path)
    return rows


class TelemetryTest(unittest.TestCase):
    def test_one_well_formed_row_per_tick(self):
        rows = _run_and_read([], ticks=12)
        self.assertEqual(len(rows), 12, "exactly one row per tick")
        self.assertEqual([r["tick"] for r in rows], list(range(1, 13)),
                         "ticks must be recorded in order, 1..N")
        for r in rows:
            self.assertEqual(r["run_id"], "t")
            self.assertEqual({a["id"] for a in r["agents"]}, {"a0", "a1"})
            for a in r["agents"]:
                for key in ("urge", "mood", "felt_mood", "memories", "cooldown"):
                    self.assertIn(key, a)

    def test_a_spoken_line_lands_in_its_tick_row(self):
        rows = _run_and_read([], ticks=30)
        spoken = [(r["tick"], u["text"])
                  for r in rows for u in r["utterances"]]
        self.assertTrue(spoken, "agents should have spoken at least once")
        self.assertTrue(all(text == "stub line" for _, text in spoken))

    def test_a_fired_event_is_recorded_in_its_tick(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=5, emotion=-0.6)
        rows = _run_and_read([ev], ticks=10)
        event_rows = [r for r in rows if r["events"]]
        self.assertEqual(len(event_rows), 1, "the event fires on exactly one tick")
        self.assertEqual(event_rows[0]["tick"], 5)
        self.assertEqual(event_rows[0]["events"][0]["name"], "flood")
        self.assertEqual(event_rows[0]["events"][0]["emotion"], -0.6)

    def test_recorded_mood_tracks_the_perturbation(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=5, emotion=-0.8)
        rows = _run_and_read([ev], ticks=10)
        before = rows[3]["agents"][0]["mood"]   # tick 4, pre-event
        after = rows[5]["agents"][0]["mood"]    # tick 6, post-event
        self.assertLess(after, before,
                        "a negative event must show up as a drop in recorded mood")

    def test_control_run_records_no_events(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=5, emotion=-0.8)
        rows = _run_and_read([ev], ticks=10, enabled=False, run_id="control")
        self.assertTrue(all(not r["events"] for r in rows),
                        "a control run's trace must contain no events")
        self.assertTrue(all(r["run_id"] == "control" for r in rows))


if __name__ == "__main__":
    unittest.main()
