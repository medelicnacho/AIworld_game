"""Grow a corpus from the project's OWN Markov substrate -- NO external model, ever.

Runs a mock town: each soul's ThoughtLoop (agent/thought.py, an order-1 word chain over its
memory + the genesis theme-phrases) drifts every tick, and the mock weaves those into speech.
We harvest both. The vocabulary is small and fixed (the genesis themes), so a char-RNN trained
on a big pile of this can learn it CLEANLY -- a voice owing nothing to DeepSeek or anyone, grown
entirely from the world's own churn.

  python homegrown/grow_corpus.py --ticks 6000   -> homegrown/corpus_markov.txt
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.agent import Agent
from agent.genesis import NAMES, _THEMES
from services.llm import MockLLM
from world.sim import World

HERE = os.path.dirname(__file__)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(HERE, "corpus_markov.txt"))
    p.add_argument("--ticks", type=int, default=6000)
    p.add_argument("--agents", type=int, default=8)
    args = p.parse_args()

    rng = random.Random(7)
    w = World()
    w.llm = MockLLM(seed=1)
    for i in range(args.agents):
        themes = rng.sample(_THEMES, 6)
        a = Agent(f"s{i}", NAMES[i % len(NAMES)], (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {NAMES[i % len(NAMES)]}.", list(themes), MockLLM(seed=i),
                  seed=i, temperament=rng.uniform(-0.5, 0.5), lifespan=10 ** 9)
        for t in themes:                       # seed memory so the chain has material from tick 0
            a.memory.write(t, tick=0, source="self", speaker_id=a.id, weight=1.0)
        w.add(a)

    seen: set[str] = set()
    lines: list[str] = []
    t0 = time.time()
    for tick in range(args.ticks):
        w.step()
        for a in w.agents:
            frag = a.thought.drift[-1] if a.thought.drift else ""
            if frag and len(frag.split()) >= 2 and frag not in seen:
                seen.add(frag); lines.append(frag)
        for _, txt in w.spoken[-1:]:            # the mock's woven speech
            if txt and len(txt) >= 8 and txt not in seen:
                seen.add(txt); lines.append(txt)

    text = "\n".join(lines) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"grew {len(lines)} unique fragments, {len(text)} chars in {time.time()-t0:.0f}s -> {args.out}")
    print("--- a taste of the world's raw markov ---")
    for ln in lines[:8]:
        print("  " + ln[:80])


if __name__ == "__main__":
    main()
