"""Events & the universal currency of the world: the Utterance.

Whether speech comes from an AI's LLM or from the user (mic/keyboard), it becomes
an Utterance and flows through the same pipe: spoken -> heard -> written to memory.
"""

from __future__ import annotations

import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Utterance:
    speaker_id: str
    text: str
    tick: int
    addressed_to: str | None = None  # agent id this is a reply to, if any
    source: str = "ai"               # "ai" | "user"
    effectiveness: float = 1.0       # speaker's grace -> how hard its words imprint
    mood: float = 0.0                # speaker's felt mood -> read as its disposition
    religion: str = ""               # speaker's faith -> the faction line
    proclamation: str = ""           # if preaching, the fundamental being proclaimed (threat target)
    belief_vec: tuple = ()           # speaker's evolving opinion vector (emergent bonding); empty in legacy mode


@dataclass(frozen=True)
class WorldEvent:
    """A perturbation in the world: something that happens TO the agents.

    This is the experiment's independent variable. Like an Utterance it enters
    agents through the same pipe (perceived -> written to memory -> reshapes
    thought, mood, and speech), but it has no speaker: it is the world acting,
    not a peer talking. Fire it at a known `tick` so an effect can be attributed
    to it, and toggle the whole schedule off to get a matched control run.
    """
    name: str                              # short id, e.g. "the_fire_dies"
    description: str                       # what the agents perceive (becomes memory)
    tick: int                              # the tick it fires on
    emotion: float = 0.0                   # emotional charge written into memory, -1..1
    urge: float = 0.4                      # how strongly it makes agents want to react
    scope: tuple[str, ...] | None = None   # agent ids it reaches; None = everyone


class EventBus:
    """Minimal pub/sub so the sim, agents, and (later) the renderer stay decoupled."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, topic: str, fn: Callable) -> None:
        self._subs[topic].append(fn)

    def publish(self, topic: str, payload) -> None:
        # Subscribers are isolated: one throwing listener (a bad renderer hook, a
        # TTS device error) must not abort the publish loop or kill the world.
        for fn in self._subs[topic]:
            try:
                fn(payload)
            except Exception:  # noqa: BLE001 -- contain, log, keep ticking
                print(f"[bus] subscriber for '{topic}' failed:", file=sys.stderr)
                traceback.print_exc()
