"""Milestone 1 demo: prove the utterance -> heard -> memory -> influence loop.

No LLM, no TTS, no 3D yet. Three agents stand near each other and talk; you can
watch phrases propagate between them, get reinforced, mutate, and be forgotten.

Run:  python main.py
      python main.py --ticks 120 --seed 7
"""

from __future__ import annotations

import argparse

from agent.agent import Agent
from world.events import EventBus
from world.sim import World


def build_world(seed: int) -> World:
    bus = EventBus()

    # debug overlay (later this is hidden; AI speech becomes audio-only via TTS)
    def on_utterance(u):
        who = {"river": "River", "ash": "Ash", "moth": "Moth"}.get(u.speaker_id, u.speaker_id)
        tag = f" @{u.addressed_to}" if u.addressed_to else ""
        print(f"  t{u.tick:>3} [{who}{tag}]: {u.text}")

    def on_memory(payload):
        agent_id, ev = payload
        print(f"        ~ {agent_id} {ev}")

    bus.subscribe("utterance", on_utterance)
    bus.subscribe("memory", on_memory)

    world = World(bus)
    world.add(Agent("river", "River", (0.0, 0.0),
                    ["the water keeps moving", "I dreamed of the deep again",
                     "everything flows downhill"], seed=seed + 1))
    world.add(Agent("ash", "Ash", (2.0, 0.0),
                    ["the fire went out hours ago", "I remember warmth",
                     "smoke rises and forgets"], seed=seed + 2))
    world.add(Agent("moth", "Moth", (1.0, 1.5),
                    ["I am drawn to any light", "wings are heavier at night",
                     "I keep circling the same thought"], seed=seed + 3))

    # seed a couple of initial memories so there's something to drift from
    world.agents[0].memory.write("the deep is cold", tick=0, source="self",
                                 speaker_id="river", emotion=-0.3)
    world.agents[1].memory.write("warmth fades", tick=0, source="self",
                                 speaker_id="ash", emotion=-0.2)
    return world


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticks", type=int, default=120)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    world = build_world(args.seed)
    print(f"=== AI World :: Milestone 1 (headless) :: seed={args.seed} ===\n")
    world.run(args.ticks)

    print("\n=== final memory state ===")
    for a in world.agents:
        print(f"\n{a.name} ({len(a.memory)} memories, mood={a.memory.mood():+.2f}):")
        for m in sorted(a.memory.items, key=lambda m: m.salience, reverse=True):
            print(f"   {m.salience:.2f}  [{m.source}]  {m.text!r}")


if __name__ == "__main__":
    main()
