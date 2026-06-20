"""The World: tick clock, spatial hearing range, and an urge-based turn scheduler.

Headless and engine-agnostic. Panda3D (or any renderer) will later just subscribe
to the event bus and draw what happens here.
"""

from __future__ import annotations

import math

from world.events import EventBus, Utterance


HEARING_RANGE = 50.0     # v1: large enough that co-located agents all hear
SPEAK_THRESHOLD = 1.0    # urge needed to grab the floor
RECENT_LINES = 5         # how many recent lines agents are told NOT to repeat


class World:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self.agents: list = []
        self.tick = 0
        self.recent: list[str] = []   # rolling buffer of the last things said

    def _remember_said(self, text: str) -> None:
        self.recent.append(text)
        del self.recent[:-RECENT_LINES]

    def add(self, agent) -> None:
        self.agents.append(agent)

    def _distance(self, a, b) -> float:
        (ax, ay), (bx, by) = a.position, b.position
        return math.hypot(ax - bx, ay - by)

    def listeners_of(self, speaker) -> list:
        return [a for a in self.agents
                if a is not speaker and self._distance(a, speaker) <= HEARING_RANGE]

    def deliver(self, u: Utterance, speaker) -> None:
        """An utterance is heard by everyone in range -> writes their memory."""
        for listener in self.listeners_of(speaker):
            listener.hear(u, self.tick, speaker_name=speaker.name)
        self._remember_said(u.text)
        self.bus.publish("utterance", u)

    def inject_user(self, text: str) -> None:
        """User input is just an utterance with source='user'."""
        u = Utterance(speaker_id="user", text=text, tick=self.tick, source="user")
        for listener in self.agents:
            listener.hear(u, self.tick, speaker_name="You")
        self._remember_said(u.text)
        self.bus.publish("utterance", u)

    def step(self) -> None:
        self.tick += 1
        # 1) subconscious + living memory for everyone
        for a in self.agents:
            for ev in a.step(self.tick):
                self.bus.publish("memory", (a.id, ev))
        # 2) urge-based turn: highest urge over threshold grabs the floor
        ready = [a for a in self.agents if a.wants_to_speak(SPEAK_THRESHOLD)]
        if ready:
            speaker = max(ready, key=lambda a: a.speak_urge)
            # tell the speaker what was just said (others' lines) so it won't echo
            recent = [t for t in self.recent if t][-RECENT_LINES:]
            u = speaker.speak(self.tick, recent=recent)
            self.deliver(u, speaker)

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()
