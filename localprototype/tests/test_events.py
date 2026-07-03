"""Tests for the world-event subsystem: the experiment's independent variable.

An event must (1) fire on exactly its scheduled tick, (2) enter agents through
the memory pipe with its emotional charge so it moves mood, (3) reach only the
agents in its scope, and (4) be cleanly toggleable so a control run (events off)
differs from a treatment run (events on) by that one variable alone.

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_events.py
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

# allow `python tests/test_events.py` from anywhere

from agent.agent import Agent
from world.events import EventBus, WorldEvent
from world.sim import World


class StubLLM:
    """Deterministic, no-network backend: every turn says the same thing."""

    def speak(self, ctx):
        return "stub line"


def _agent(agent_id: str, seed: int, llm) -> Agent:
    return Agent(agent_id, agent_id.upper(), (0.0, 0.0), "a persona",
                 ["a seed phrase"], llm, seed=seed, temperament=0.0)


def _world_with(events, enabled=True):
    bus = EventBus()
    fired = []
    bus.subscribe("world_event", fired.append)
    world = World(bus, events=events, events_enabled=enabled)
    world.add(_agent("a0", 1, StubLLM()))
    world.add(_agent("a1", 2, StubLLM()))
    return world, fired


class WorldEventTest(unittest.TestCase):
    def test_event_fires_on_its_scheduled_tick(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=5, emotion=-0.6)
        world, fired = _world_with([ev])

        with redirect_stderr(io.StringIO()):
            world.run(4)
        self.assertEqual(fired, [], "event must not fire before its tick")

        with redirect_stderr(io.StringIO()):
            world.step()   # tick 5
        self.assertEqual([e.name for e in fired], ["flood"],
                         "event must fire exactly once, on its scheduled tick")

    def test_event_writes_memory_with_its_emotional_charge(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=1, emotion=-0.6)
        world, _ = _world_with([ev])

        with redirect_stderr(io.StringIO()):
            world.step()   # tick 1 fires the event

        for a in world.agents:
            mems = [m for m in a.memory.items if m.text == ev.description]
            self.assertTrue(mems, f"{a.id} should remember the event")
            self.assertEqual(mems[0].emotion, ev.emotion)
            self.assertEqual(mems[0].source, "event")
        # a charged negative event must pull mood downward
        self.assertLess(world.agents[0].memory.mood(), 0.0,
                        "a negative event should darken mood")

    def test_event_raises_the_urge_to_react(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=1,
                        emotion=-0.6, urge=0.5)
        world, _ = _world_with([ev])
        before = world.agents[0].speak_urge

        with redirect_stderr(io.StringIO()):
            world.inject_event(ev)   # isolate the urge bump from per-tick drift
        self.assertGreaterEqual(world.agents[0].speak_urge - before, 0.5)
        self.assertEqual(world.agents[0].last_event_text, ev.description)

    def test_scope_limits_who_perceives_the_event(self):
        ev = WorldEvent("whisper", "a voice meant only for one", tick=1,
                        emotion=-0.3, scope=("a0",))
        world, _ = _world_with([ev])

        with redirect_stderr(io.StringIO()):
            world.step()

        self.assertTrue(any(m.text == ev.description for m in world.agents[0].memory.items),
                        "the in-scope agent must perceive the event")
        self.assertFalse(any(m.text == ev.description for m in world.agents[1].memory.items),
                         "an out-of-scope agent must NOT perceive the event")

    def test_events_can_be_toggled_off_for_a_control_run(self):
        ev = WorldEvent("flood", "the water is rising fast", tick=1, emotion=-0.6)
        world, fired = _world_with([ev], enabled=False)

        with redirect_stderr(io.StringIO()):
            world.run(10)

        self.assertEqual(fired, [], "no event may fire when events are disabled")
        for a in world.agents:
            self.assertFalse(any(m.text == ev.description for m in a.memory.items),
                             "a control run must not perceive any event")

    def test_a_perceived_event_surfaces_in_the_next_speech_turn(self):
        captured = {}

        class CapturingLLM:
            def speak(self, ctx):
                captured["event"] = ctx.event
                return "reacting"

        ev = WorldEvent("flood", "the water is rising fast", tick=1,
                        emotion=-0.6, urge=5.0)   # big urge -> speaks promptly
        bus = EventBus()
        world = World(bus, events=[ev])
        world.add(_agent("a0", 1, CapturingLLM()))

        with redirect_stderr(io.StringIO()):
            world.run(2)   # tick 1 fires, the charged agent speaks tick 1 or 2

        self.assertEqual(captured.get("event"), ev.description,
                         "the event should reach the LLM as the thing on the mind")


if __name__ == "__main__":
    unittest.main()
