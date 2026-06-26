"""Regression tests for fault containment: the world must outlive its failures.

A world that claims to live cannot be killed by one bad packet. These tests
inject the two failure modes the architecture is most exposed to and assert the
clock keeps ticking:

  1. an LLM backend that throws on every turn (timeout / dropped socket / 5xx)
  2. an event-bus subscriber that throws on every utterance (bad renderer/TTS hook)

Run:  python -m unittest discover -s tests        # from the prototype/ dir
      python tests/test_fault_containment.py
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr

# allow `python tests/test_fault_containment.py` from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import Agent
from world.events import EventBus
from world.sim import World


class ExplodingLLM:
    """A backend that is down 100% of the time."""

    def __init__(self) -> None:
        self.calls = 0

    def speak(self, ctx):
        self.calls += 1
        raise RuntimeError("simulated backend 500 / dropped socket")


def _charged_agent(agent_id: str, seed: int, llm) -> Agent:
    """An agent primed to want to speak soon (charged, low-mood memory)."""
    a = Agent(agent_id, agent_id.upper(), (0.0, 0.0), "a persona",
              ["a charged seed phrase about the cold deep"], llm,
              seed=seed, temperament=-0.4)
    a.memory.write("the deep is cold and dark", tick=0, source="self")
    return a


class FaultContainmentTest(unittest.TestCase):
    def test_world_survives_a_backend_that_always_throws(self):
        """Every LLM call raises, yet the clock advances the full run."""
        llm = ExplodingLLM()
        bus = EventBus()
        delivered = []
        bus.subscribe("utterance", delivered.append)

        world = World(bus)
        world.add(_charged_agent("a0", 1, llm))
        world.add(_charged_agent("a1", 2, llm))

        with redirect_stderr(io.StringIO()):   # failures log to stderr; keep test output clean
            world.run(40)

        self.assertEqual(world.tick, 40, "the world clock must reach the full run")
        self.assertGreater(llm.calls, 0, "agents should actually have attempted to speak")
        # failed turns degrade to a silent beat rather than crashing
        self.assertTrue(all(u.text == "..." for u in delivered),
                        "a failed LLM turn should degrade to '...'")

    def test_throwing_subscriber_does_not_abort_the_publish_loop(self):
        """One bad listener must not starve the good listeners or kill the world."""
        bus = EventBus()
        good = []

        def bad_subscriber(_payload):
            raise ValueError("bad renderer hook")

        # order matters: the bad one runs first, the good one must still fire
        bus.subscribe("utterance", bad_subscriber)
        bus.subscribe("utterance", good.append)

        world = World(bus)
        world.add(_charged_agent("a0", 1, ExplodingLLM()))
        world.add(_charged_agent("a1", 2, ExplodingLLM()))

        with redirect_stderr(io.StringIO()):
            world.run(40)

        self.assertEqual(world.tick, 40)
        self.assertGreater(len(good), 0,
                           "the well-behaved subscriber must still receive deliveries")

    def test_bus_logs_subscriber_failures_to_stderr(self):
        """Containment is loud, not silent: failures are diagnosable on stderr."""
        bus = EventBus()
        bus.subscribe("ping", lambda _p: (_ for _ in ()).throw(ValueError("boom")))

        err = io.StringIO()
        with redirect_stderr(err):
            bus.publish("ping", None)   # must not raise

        self.assertIn("subscriber for 'ping' failed", err.getvalue())
        self.assertIn("ValueError", err.getvalue())


if __name__ == "__main__":
    unittest.main()
