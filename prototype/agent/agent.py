"""An Agent ties together memory + subconscious thought + LLM speech.

Milestone 2: the placeholder phrase-picker is gone. Each tick the subconscious
(Markov ThoughtLoop) drifts over the agent's memory; when the agent grabs the
floor it packs that drift + recalled memories + whoever just spoke to it into a
SpeechContext and asks the LLM to actually talk. Hearing still writes memory,
so speech keeps reshaping future thought.
"""

from __future__ import annotations

import random

from agent.memory import MemoryStore
from agent.thought import ThoughtLoop
from services.llm import SpeechContext
from world.events import Utterance

TANGENT_CHANCE = 0.35   # chance an agent ignores the last line and speaks fresh


class Agent:
    def __init__(self, agent_id: str, name: str, position: tuple[float, float],
                 persona: str, phrases: list[str], llm,
                 seed: int | None = None) -> None:
        self.id = agent_id
        self.name = name
        self.position = position
        self.persona = persona
        self.phrases = phrases            # persona seed material for the drift
        self.llm = llm
        self.memory = MemoryStore(seed=seed)
        self.thought = ThoughtLoop(seed=seed)
        self.speak_urge = 0.0
        self.cooldown = 0
        self.last_heard_from: str | None = None
        self.last_heard_text: str | None = None
        self.last_heard_name: str | None = None
        self._rng = random.Random(seed)

    # --- per-tick subconscious ---------------------------------------------
    def step(self, now: int) -> list[str]:
        events = self.memory.tick(now)
        if self.cooldown > 0:
            self.cooldown -= 1
        self.thought.learn(self.memory.items, self.phrases)
        self.thought.step()
        # urge drifts upward; charged memory pushes it faster (the "impulse")
        self.speak_urge += 0.05 + 0.1 * abs(self.memory.mood())
        self.speak_urge += self._rng.uniform(0, 0.05)
        return events

    # --- hearing: this is where influence enters --------------------------
    def hear(self, u: Utterance, now: int, speaker_name: str | None = None) -> None:
        if u.speaker_id == self.id:
            return
        self.memory.write(u.text, tick=now, source=u.source, speaker_id=u.speaker_id)
        self.last_heard_from = u.speaker_id
        self.last_heard_text = u.text
        self.last_heard_name = speaker_name or u.speaker_id
        if u.addressed_to == self.id or u.source == "user":
            self.speak_urge += 0.6  # being addressed makes you want to reply

    # --- speaking ----------------------------------------------------------
    def wants_to_speak(self, threshold: float) -> bool:
        return self.cooldown == 0 and self.speak_urge >= threshold

    def speak(self, now: int, recent: list[str] | None = None) -> Utterance:
        # Tangent: sometimes drop the thread and speak fresh from your own mind,
        # so the conversation diverges instead of collapsing into one topic.
        tangent = (self.last_heard_text is None
                   or self._rng.random() < TANGENT_CHANCE)

        if tangent:
            # recall biased to THIS agent's theme, not whatever was just heard
            query = self._rng.choice(self.phrases)
            reply_name = reply_text = addressed = None
        else:
            query = self.last_heard_text
            reply_name, reply_text = self.last_heard_name, self.last_heard_text
            addressed = self.last_heard_from

        recalled = self.memory.recall(k=3, query=query)
        ctx = SpeechContext(
            name=self.name,
            persona=self.persona,
            mood=self.memory.mood(),
            drift=self.thought.current(3),
            memories=[m.text for m in recalled],
            reply_to_name=reply_name,
            reply_to_text=reply_text,
            recent=list(recent or []),
        )
        text = self.llm.speak(ctx)

        u = Utterance(speaker_id=self.id, text=text, tick=now,
                      addressed_to=addressed, source="ai")
        self.memory.write(text, tick=now, source="self", speaker_id=self.id)
        self.speak_urge = 0.0
        self.cooldown = 3
        # speaking consumes the prompt that triggered it
        self.last_heard_text = None
        self.last_heard_from = None
        return u
