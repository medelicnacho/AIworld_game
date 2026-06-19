"""Milestone 2 demo: Markov subconscious drift -> local LLM speech.

Each agent's subconscious drifts over its (mutating, forgetting) memory; when it
grabs the floor it asks a local LLM (Ollama) to actually talk about what it's
thinking and reply to whoever just spoke. Falls back to a MockLLM if no model.

Run:  python main.py                       # auto-detect Ollama
      python main.py --backend mock        # no model, instant
      python main.py --model dolphin-mistral:latest --ticks 40
      python main.py --think               # also print subconscious drift
"""

from __future__ import annotations

import argparse

from agent.agent import Agent
from services.llm import DEFAULT_MODEL, make_llm
from world.events import EventBus
from world.sim import World

PERSONAS = [
    ("river", "River", (0.0, 0.0),
     "You are slow, watery, and melancholic; you think in tides and depths.",
     ["the water keeps moving", "I dreamed of the deep again",
      "everything flows downhill"]),
    ("ash", "Ash", (2.0, 0.0),
     "You are burnt-out and wry; you speak of warmth that is already gone.",
     ["the fire went out hours ago", "I remember warmth",
      "smoke rises and forgets"]),
    ("moth", "Moth", (1.0, 1.5),
     "You are restless and obsessive, pulled toward light and circling thoughts.",
     ["I am drawn to any light", "wings are heavier at night",
      "I keep circling the same thought"]),
]


def build_world(llm, seed: int, show_think: bool) -> World:
    bus = EventBus()
    names = {p[0]: p[1] for p in PERSONAS}

    def on_utterance(u):
        who = names.get(u.speaker_id, u.speaker_id)
        tag = f" @{u.addressed_to}" if u.addressed_to else ""
        print(f"  t{u.tick:>3} [{who}{tag}]: {u.text}")

    def on_memory(payload):
        agent_id, ev = payload
        print(f"        ~ {agent_id} {ev}")

    bus.subscribe("utterance", on_utterance)
    if show_think:
        bus.subscribe("memory", on_memory)

    world = World(bus)
    for i, (aid, name, pos, persona, phrases) in enumerate(PERSONAS):
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
    p.add_argument("--backend", choices=["auto", "ollama", "mock"], default="auto")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--think", action="store_true",
                   help="also print memory mutation/forget events")
    args = p.parse_args()

    llm = make_llm(backend=args.backend, model=args.model, seed=args.seed)
    world = build_world(llm, args.seed, args.think)
    print(f"\n=== AI World :: Milestone 2 :: seed={args.seed} ===\n")
    world.run(args.ticks)

    print("\n=== final memory state ===")
    for a in world.agents:
        print(f"\n{a.name} ({len(a.memory)} memories, mood={a.memory.mood():+.2f}):")
        for m in sorted(a.memory.items, key=lambda m: m.salience, reverse=True)[:8]:
            print(f"   {m.salience:.2f}  [{m.source}]  {m.text!r}")


if __name__ == "__main__":
    main()
