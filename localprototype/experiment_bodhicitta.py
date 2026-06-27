"""MAHĀYĀNA BRICK -- bodhicitta: compassion as an AIM, not a reaction.

Reactive warmth (Stage 6) waits to be challenged or addressed. Bodhicitta SEEKS: a soul
so moved remembers who is suffering and proactively turns back toward them to comfort
them, even unprompted, even when they are not talking to it.

Setup: a soul (Bram) overhears another (Silas) suffering -- a grieving line, not aimed at
Bram. Time passes; Bram is not freshly addressed. Bram takes the floor with its own
preoccupation available. We compare:
  bodhicitta OFF -> Bram speaks its own thing; the overheard sufferer is not its concern.
  bodhicitta ON  -> Bram turns BACK to Silas and offers comfort -- proactively.

Measure: warmth of Bram's line (toward the sufferer), and whether it's directed at Silas.

Run:  python experiment_bodhicitta.py --llm ollama --model gemma3:4b
"""

from __future__ import annotations

import argparse

from agent import compassion as C
from agent.affect import warmth
from agent.agent import Agent
from services.llm import MockLLM, OllamaLLM


def helper(bodhicitta: float, llm) -> Agent:
    b = Agent("B", "Bram", (0, 0), "You are Bram, a steady baker.",
              ["I mind the morning bread", "the festival's coming up"], llm,
              seed=7, temperament=0.2)
    b.bodhicitta = bodhicitta
    # Bram overheard Silas grieving a while ago (felt mood low), not addressed to Bram
    b._others_mood["S"] = -0.5
    b._others_name["S"] = "Silas"
    return b


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    C.BODHICITTA_CHANCE = 1.0   # make the proactive turn deterministic for the A/B

    print(f"\n=== Bodhicitta: compassion as an aim ({args.llm}"
          f"{'/'+args.model if args.model else ''}) ===")
    print("  Bram overheard Silas grieving (mood -0.5), not addressed to him. Bram now "
          "takes the floor, not freshly prompted.\n")
    for label, bod in [("bodhicitta OFF", 0.0), ("bodhicitta ON ", 0.8)]:
        b = helper(bod, llm)
        ctx, addressed, _ = b.prepare_speech(recent=[])
        line = b.speak(now=2).text
        turned = "-> turns to Silas" if addressed == "S" else "-> speaks its own thing"
        print(f"  {label}: warmth {warmth(line):+.2f}  {turned}")
        print(f"     {line}")
    print("\n  -> bodhicitta should make Bram PROACTIVELY turn to comfort Silas (warmer, "
          "directed at the sufferer); without it, Bram tends to its own day.")


if __name__ == "__main__":
    main()
