"""PLURALITY -- does drawing souls as distinct ARCHETYPES raise cross-soul distinctness?

The same base souls (identical persona + seed, so the uniform arm is maximally alike),
each made to speak a couple of lines. UNIFORM: no archetype (the old flat cast). ARCHETYPE:
each soul stamped with a different archetype (Grasper / Sage / Lover / Skeptic ...), which
gives it a distinct voice, faculty profile, and value-lean.

Distinctness = 1 - mean pairwise cosine of the souls' speech (higher = more different from
each other). The claim: archetypes make the cast genuinely plural, which is the
prerequisite for a Mind that is a chorus rather than one bland average.

Run:  python experiment_archetypes.py --llm ollama --model gemma3:4b
"""

from __future__ import annotations

import argparse
import statistics

from agent import archetype as _arch
from agent.agent import Agent
from services.embed import score
from services.llm import MockLLM, OllamaLLM

N = 4
LINES = 2


def cast(llm, archetypes):
    souls = []
    for i in range(N):
        a = Agent(f"s{i}", f"Soul{i}", (0, 0),
                  "You are an ordinary townsperson going about your day.",
                  ["the morning bread", "the price of wool", "the mended cart"],
                  llm, seed=100 + i, temperament=0.0)
        if archetypes:
            _arch.apply(a, _arch.ARCHETYPES[i])
        souls.append(a)
    return souls


def speech_of(souls) -> list[str]:
    out = []
    for a in souls:
        lines = [a.speak(now=t).text for t in range(1, LINES + 1)]
        out.append(" ".join(lines))
    return out


def distinctness(texts) -> float:
    sims = [score(texts[i], texts[j]) for i in range(len(texts)) for j in range(i + 1, len(texts))]
    return 1.0 - (statistics.fmean(sims) if sims else 0.0)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.8, model=args.model) if args.model else OllamaLLM(temperature=0.8)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    uniform = speech_of(cast(llm, archetypes=False))
    archety = speech_of(cast(llm, archetypes=True))
    du, da = distinctness(uniform), distinctness(archety)

    print(f"\n=== Plurality via archetypes ({args.llm}{'/'+args.model if args.model else ''}) ===\n")
    print("  UNIFORM cast (no archetype):")
    for t in uniform:
        print(f"     · {t[:110]}")
    print(f"\n  ARCHETYPE cast ({', '.join(_arch.ARCHETYPES[i].name for i in range(N))}):")
    for i, t in enumerate(archety):
        print(f"     · [{_arch.ARCHETYPES[i].name}] {t[:100]}")
    print(f"\n  cross-soul DISTINCTNESS (higher = more plural):")
    print(f"     uniform {du:+.3f}   ->   archetype {da:+.3f}   (Δ {da - du:+.3f})")
    print("  -> " + ("PLURAL: archetypes make the souls genuinely more distinct from each other."
                    if da > du + 0.02 else
                    "no clear gain (the base model may be flattening the voices; check samples)."))


if __name__ == "__main__":
    main()
