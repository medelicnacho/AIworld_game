"""Per-tick telemetry: the instrument's data recorder.

Behavior change is the dependent variable of every run, so it must leave a
machine-readable trace -- not just scroll past on stdout. This Recorder
subscribes to the same event bus the renderer uses and writes one JSON object
per tick to a JSONL file: each agent's mood / urge / memory-size, the lines
spoken, any world event that fired, and memory mutations/forgets.

Because it only listens on the bus, recording is decoupled from the sim: turning
it on or off changes nothing about how the world runs. Load the file afterwards
(pandas, jq, a notebook) to compare a treatment run (events on) against its
matched control (events off) and put a number on the difference.

    {"run_id": "...", "tick": 20, "agents": [{"id": "river", "mood": -0.31, ...}],
     "utterances": [...], "events": [{"name": "the_fire_dies", ...}], "memory": [...]}
"""

from __future__ import annotations

import json

from services import factions


def felt_mood(agent) -> float:
    """The agent's disposition (temperament anchored, lived mood nudging)."""
    return agent.felt_mood()


class Recorder:
    """Writes one JSONL row per tick by listening on the world's event bus."""

    def __init__(self, path: str, world, run_id: str | None = None) -> None:
        self.world = world
        self.run_id = run_id
        self._fh = open(path, "w", encoding="utf-8")
        self._utterances: list[dict] = []
        self._events: list[dict] = []
        self._memory: list[dict] = []

        bus = world.bus
        bus.subscribe("utterance", self._on_utterance)
        bus.subscribe("world_event", self._on_world_event)
        bus.subscribe("memory", self._on_memory)
        bus.subscribe("tick", self._on_tick)   # the flush boundary

    # --- accumulate everything that happens during the tick ----------------
    def _on_utterance(self, u) -> None:
        self._utterances.append({
            "speaker": u.speaker_id, "text": u.text,
            "addressed_to": u.addressed_to, "source": u.source,
        })

    def _on_world_event(self, ev) -> None:
        self._events.append({
            "name": ev.name, "description": ev.description, "emotion": ev.emotion,
        })

    def _on_memory(self, payload) -> None:
        agent_id, ev = payload
        self._memory.append({"agent": agent_id, "event": ev})

    # --- flush one row at the tick boundary --------------------------------
    def _on_tick(self, tick: int) -> None:
        row = {
            "tick": tick,
            "agents": [{
                "id": a.id,
                "urge": round(a.speak_urge, 4),
                "mood": round(a.memory.mood(), 4),       # raw memory valence
                "felt_mood": round(felt_mood(a), 4),     # temperament-blended
                "memories": len(a.memory),
                "cooldown": a.cooldown,
                "grace": round(a.grace, 3),   # standing with the Creator (0..1)
                "age": a.age,
                "belief": a.belief,           # the stance the agent argues from
                "conviction": round(a.conviction, 3),
                "identity_investment": round(getattr(a, "identity_investment", 0.0), 3),
                "dissonance": round(getattr(a, "dissonance", 0.0), 3),
                "hostility": {k: round(v, 1) for k, v in a.hostility.items()},
                "relationship": dict(getattr(a, "relationship", {})),
                "at_war_with": [o for o in a.hostility if a.is_at_war_with(o)],
                # how this agent feels about each other agent (-1 foe .. 1 kin);
                # cluster these over a run to watch factions crystallize
                "affinity": {k: round(v, 3) for k, v in a.affinity.items()},
            } for a in self.world.agents],
            # whole-world faction metrics this tick: cluster modularity and how
            # well the blocs reduce to the fixed faith/temperament labels. Plot
            # these over a run to see (or fail to see) factions crystallize.
            "factions": factions.summary(self.world.agents),
            "utterances": self._utterances,
            "events": self._events,
            "memory": self._memory,
        }
        if self.run_id is not None:
            row = {"run_id": self.run_id, **row}
        self._fh.write(json.dumps(row) + "\n")
        self._fh.flush()
        self._utterances, self._events, self._memory = [], [], []

    def close(self) -> None:
        self._fh.close()

    # so it can be used as a context manager: `with Recorder(...) as rec:`
    def __enter__(self) -> "Recorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
