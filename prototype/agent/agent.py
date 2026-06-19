"""An Agent ties together memory + (eventual) thought + speech.

Milestone 1: speech is NOT an LLM yet. To prove the influence loop, an agent
composes an utterance from a small persona phrase pool + something it recalls
(often something it *heard* from another agent). That's enough to watch ideas
propagate and mutate between agents -- the LLM/Markov/TTS slot in later.
"""

from __future__ import annotations

import random

from agent.memory import MemoryStore
from world.events import Utterance


class Agent:
    def __init__(self, agent_id: str, name: str, position: tuple[float, float],
                 phrases: list[str], seed: int | None = None) -> None:
        self.id = agent_id
        self.name = name
        self.position = position
        self.phrases = phrases
        self.memory = MemoryStore(seed=seed)
        self.speak_urge = 0.0
        self.cooldown = 0
        self.last_heard_from: str | None = None
        self._rng = random.Random(seed)

    # --- per-tick subconscious (placeholder for the Markov loop) -----------
    def step(self, now: int) -> list[str]:
        events = self.memory.tick(now)
        if self.cooldown > 0:
            self.cooldown -= 1
        # urge drifts upward; charged memory pushes it faster (the "impulse")
        self.speak_urge += 0.05 + 0.1 * abs(self.memory.mood())
        self.speak_urge += self._rng.uniform(0, 0.05)
        return events

    # --- hearing: this is where influence enters --------------------------
    def hear(self, u: Utterance, now: int) -> None:
        if u.speaker_id == self.id:
            return  # don't re-hear yourself here; speaking already self-wrote
        self.memory.write(u.text, tick=now, source=u.source, speaker_id=u.speaker_id)
        self.last_heard_from = u.speaker_id
        if u.addressed_to == self.id or u.source == "user":
            self.speak_urge += 0.6  # being addressed makes you want to reply

    # --- speaking ----------------------------------------------------------
    def wants_to_speak(self, threshold: float) -> bool:
        return self.cooldown == 0 and self.speak_urge >= threshold

    def speak(self, now: int) -> Utterance:
        base = self._rng.choice(self.phrases)
        recalled = self.memory.recall(k=3)
        # weave in a recalled idea ~half the time -> ideas spread & recombine
        if recalled and self._rng.random() < 0.6:
            frag = self._rng.choice(recalled).text
            text = f"{base} ... {frag}"
        else:
            text = base

        u = Utterance(speaker_id=self.id, text=text, tick=now,
                      addressed_to=self.last_heard_from, source="ai")
        self.memory.write(text, tick=now, source="self", speaker_id=self.id)
        self.speak_urge = 0.0
        self.cooldown = 3
        return u
