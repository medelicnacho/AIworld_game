"""Milestone 3 demo: subconscious drift -> LLM speech -> spoken aloud via TTS.

Each agent's subconscious (Markov) drifts over its mutating/forgetting memory;
on its turn it asks an LLM (Claude / Ollama) to say one short line and reply to
whoever just spoke; the line is SPOKEN with a per-agent Piper voice. AI speech is
audio-only by default -- you hear the agents, you don't read them. Hearing still
writes memory, so speech keeps reshaping thought.

Run:  python main.py                       # Claude if key set, else Ollama/Mock; audio on
      python main.py --show-text           # also print the lines (debug overlay)
      python main.py --no-audio            # silent (text only, for headless)
      python main.py --backend mock --no-audio --ticks 20
"""

from __future__ import annotations

import argparse

from agent.agent import Agent
from services.llm import make_llm
from services.tts import Voice, make_tts
from world.events import EventBus
from world.sim import World

# (id, name, position, persona, seed phrases, voice)
PERSONAS = [
    ("river", "River", (0.0, 0.0),
     "You are slow, watery, and melancholic; you think in tides and depths.",
     ["the water keeps moving", "I dreamed of the deep again",
      "everything flows downhill"],
     Voice("en_GB-alan-medium.onnx", length_scale=1.15)),   # calm, slow
    ("ash", "Ash", (2.0, 0.0),
     "You are burnt-out and wry; you speak of warmth that is already gone.",
     ["the fire went out hours ago", "I remember warmth",
      "smoke rises and forgets"],
     Voice("en_US-ryan-medium.onnx", length_scale=1.05)),   # flat, dry
    ("moth", "Moth", (1.0, 1.5),
     "You are restless and obsessive, pulled toward light and circling thoughts.",
     ["I am drawn to any light", "wings are heavier at night",
      "I keep circling the same thought"],
     Voice("en_US-amy-medium.onnx", length_scale=0.95)),    # quicker, restless
]


def build_world(llm, tts, seed: int, show_think: bool, show_text: bool) -> World:
    bus = EventBus()
    names = {p[0]: p[1] for p in PERSONAS}
    voices = {p[0]: p[5] for p in PERSONAS}

    def on_utterance(u):
        who = names.get(u.speaker_id, u.speaker_id)
        tag = f" @{u.addressed_to}" if u.addressed_to else ""
        if show_text:
            print(f"  t{u.tick:>3} [{who}{tag}]: {u.text}")
        else:  # audio-only: show who is speaking, not the words
            print(f"  t{u.tick:>3} \U0001f50a {who}{tag} ...")
        voice = voices.get(u.speaker_id)
        if voice is not None:
            tts.speak(u.text, voice)  # blocking -> paces turns to speech

    def on_memory(payload):
        agent_id, ev = payload
        print(f"        ~ {agent_id} {ev}")

    bus.subscribe("utterance", on_utterance)
    if show_think:
        bus.subscribe("memory", on_memory)

    world = World(bus)
    for i, (aid, name, pos, persona, phrases, _voice) in enumerate(PERSONAS):
        world.add(Agent(aid, name, pos, persona, phrases, llm, seed=seed + i + 1))

    world.agents[0].memory.write("the deep is cold", tick=0, source="self",
                                 speaker_id="river", emotion=-0.3)
    world.agents[1].memory.write("warmth fades", tick=0, source="self",
                                 speaker_id="ash", emotion=-0.2)
    return world


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticks", type=int, default=60)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--backend", choices=["auto", "claude", "ollama", "mock"],
                   default="auto")
    p.add_argument("--model", default=None,
                   help="override model id (defaults per backend)")
    p.add_argument("--no-audio", action="store_true", help="disable TTS playback")
    p.add_argument("--show-text", action="store_true",
                   help="print the spoken lines (debug overlay; off = audio-only)")
    p.add_argument("--think", action="store_true",
                   help="also print memory mutation/forget events")
    args = p.parse_args()

    llm = make_llm(backend=args.backend, model=args.model, seed=args.seed)
    tts = make_tts(enabled=not args.no_audio)
    world = build_world(llm, tts, args.seed, args.think, args.show_text)
    print(f"\n=== AI World :: Milestone 3 :: seed={args.seed} ===\n")
    world.run(args.ticks)

    print("\n=== final memory state ===")
    for a in world.agents:
        print(f"\n{a.name} ({len(a.memory)} memories, mood={a.memory.mood():+.2f}):")
        for m in sorted(a.memory.items, key=lambda m: m.salience, reverse=True)[:8]:
            print(f"   {m.salience:.2f}  [{m.source}]  {m.text!r}")


if __name__ == "__main__":
    main()
