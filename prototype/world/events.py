"""Events & the universal currency of the world: the Utterance.

Whether speech comes from an AI's LLM or from the user (mic/keyboard), it becomes
an Utterance and flows through the same pipe: spoken -> heard -> written to memory.
"""

from __future__ import annotations

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


class EventBus:
    """Minimal pub/sub so the sim, agents, and (later) the renderer stay decoupled."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, topic: str, fn: Callable) -> None:
        self._subs[topic].append(fn)

    def publish(self, topic: str, payload) -> None:
        for fn in self._subs[topic]:
            fn(payload)
