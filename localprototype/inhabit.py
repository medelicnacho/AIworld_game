"""The inhabitable self -- the integration the five stages built toward.

ONE soul, full stack, running perpetually: it remembers and forgets (memory), feels
(affect), relates to its own memory (reflect), takes stock of who it is becoming and
speaks from it (self-model), and forms a bond toward YOU as you speak to it (bonds).
A self for an LLM to inhabit. Run it and watch the self keep re-deriving itself; speak
to it with --you "…" lines injected on a schedule, and watch it come to know you.

Run:  python inhabit.py --llm ollama --model gemma3:4b
      python inhabit.py                       # mock (plumbing only)
"""

from __future__ import annotations

import argparse
import random

from agent import genesis as _genesis
from agent import self_model as _sm
from agent.agent import Agent
from agent.bond import describe
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM
from world.sim import World

TICKS = 40
CONSOLIDATE_EVERY = 8
REFLECT_EVERY = 6
YOU_LINES = {7: "I am here with you. I have watched over you a long while.",
             19: "Tell me, who are you becoming?",
             31: "I will not forget you, whatever happens."}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=3)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.85, model=args.model) if args.model else OllamaLLM(temperature=0.85)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    w = World()
    w.hearing_range = 1e12
    w.llm = llm
    rng = random.Random(args.seed)
    print("summoning a soul...", flush=True)
    ch = _genesis.generate_character(llm, rng, rng.choice(_genesis.SEED_CONCEPTS))
    soul = Agent("soul", ch.name, (0.0, 0.0), "", [], llm, seed=args.seed,
                 lifespan=10 ** 9)
    _genesis.seed_agent(soul, ch)          # bonds + self-model + opinion + story
    soul.concept_speech = True
    soul.reflect_enabled = True
    w.add(soul)
    print(f"  {soul.name} wakes.\n--- a life ---", flush=True)

    def on_utt(u):
        if u.speaker_id == soul.id:
            print(f"  [{w.tick:>2}] {soul.name}: {u.text}", flush=True)
        elif u.source == "user":
            print(f"  [{w.tick:>2}] YOU: {u.text}", flush=True)
    w.bus.subscribe("utterance", on_utt)

    for t in range(1, TICKS + 1):
        if t in YOU_LINES:
            w.inject_user(YOU_LINES[t])
        w.run(1)
        if t % REFLECT_EVERY == 0:
            reflect(soul, llm, t)
        if t % CONSOLIDATE_EVERY == 0:
            s = _sm.consolidate(soul, llm, t)
            if s:
                print(f"     ~ {soul.name} takes stock: {s}", flush=True)

    print(f"\n--- who {soul.name} became ---")
    print(f"  self-model: {soul.self_model}")
    you = soul.bonds.get("user")
    if you:
        print(f"  toward you: {describe(you, 'you')}  (trust {you.trust:+.2f})")


if __name__ == "__main__":
    main()
