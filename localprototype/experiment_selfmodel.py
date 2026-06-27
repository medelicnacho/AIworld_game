"""STAGE 3 -- the self-model loop. Does perpetual self-referential consolidation
produce a SELF: a sense of who-I-am that stays coherent yet drifts (an attractor, not
an essence -- anatta), differs between souls, and survives a shock then re-coheres?

Each soul periodically consolidates a one-line self-model from its streams; that line
feeds back into its prompt. We run several souls, put one through the grief protocol,
and measure (semantically, via embeddings):

  COHERENCE      a soul's successive self-models stay similar (a persisting self)...
  DRIFT          ...but not identical (a process, not a fixed essence) -- anatta.
  DISTINCTNESS   different souls' selves are MORE different from each other than a
                 soul is from its own past (selves individuate, don't homogenise).
  SELF-REFERENCE the soul's SPEECH leans toward its OWN self-model more than another's
                 (it actually speaks from the self it formed).
  RE-COHESION    the focal soul's self-model shifts around the loss, then settles.

Run:  python experiment_selfmodel.py --llm ollama --model gemma3:1b
      python experiment_selfmodel.py                     # mock: plumbing only
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent import genesis as _genesis
from agent import self_model as _sm
from agent.agent import Agent
from services.embed import score
from services.llm import MockLLM, OllamaLLM
from world.events import WorldEvent
from world.sim import World

N = 3
TICKS = 48
CONSOLIDATE_EVERY = 8
LOSS_TICK = 18
LOSS = WorldEvent("loss", "Your dearest friend has died in the night.", LOSS_TICK,
                  emotion=-0.9, urge=0.8)


def build(seed: int, llm) -> World:
    w = World()
    w.hearing_range = 1e12
    w.llm = llm
    rng = random.Random(seed)
    concepts = rng.sample(_genesis.SEED_CONCEPTS, N)
    chars = [_genesis.generate_character(llm, rng, concepts[i]) for i in range(N)]
    _genesis.dedupe_names(chars, rng)
    for i, ch in enumerate(chars):
        a = Agent(f"s{i}", ch.name, (i * 15.0, 0.0), "", [], llm, seed=seed + i + 1,
                  lifespan=10 ** 9)
        _genesis.seed_agent(a, ch)        # sets self_model_enabled
        a.concept_speech = True
        w.add(a)
    return w


def mean_consecutive(hist: list[str]) -> float:
    sims = [score(hist[i], hist[i + 1]) for i in range(len(hist) - 1)]
    return statistics.fmean(sims) if sims else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=5)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.8, model=args.model) if args.model else OllamaLLM(temperature=0.8)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    print("authoring souls...", flush=True)
    w = build(args.seed, llm)
    focal = w.agents[0]
    names = {a.id: a.name for a in w.agents}
    focal_lines: list[str] = []

    def on_utt(u):
        if u.speaker_id == focal.id:
            focal_lines.append(u.text)
    w.bus.subscribe("utterance", on_utt)

    print(f"focal soul: {focal.name}\n--- run ---", flush=True)
    for t in range(1, TICKS + 1):
        if t == LOSS_TICK:
            focal.perceive(LOSS, t)
        w.run(1)
        if t % CONSOLIDATE_EVERY == 0:
            for a in w.agents:
                if a.self_model_enabled:
                    _sm.consolidate(a, llm, t)
            print(f"  [t={t}] {focal.name} self-model: {focal.self_model}", flush=True)

    print("\n=== Stage 3: the self-model loop ===")
    for a in w.agents:
        print(f"\n  {a.name} -- self-model evolution:")
        for s in a.self_model_history:
            print(f"     · {s}")

    within = [mean_consecutive(a.self_model_history) for a in w.agents
              if len(a.self_model_history) > 1]
    within_mean = statistics.fmean(within) if within else 0.0
    latest = [a.self_model_history[-1] for a in w.agents if a.self_model_history]
    cross = [score(latest[i], latest[j]) for i in range(len(latest))
             for j in range(i + 1, len(latest))]
    cross_mean = statistics.fmean(cross) if cross else 0.0

    print("\n  MEASURES (semantic):")
    print(f"     COHERENCE   within-soul consecutive self-model similarity: {within_mean:+.3f}")
    print(f"     DISTINCTNESS cross-soul self-model similarity:             {cross_mean:+.3f}")
    coherent = within_mean > 0.45
    drifts = within_mean < 0.97
    distinct = within_mean > cross_mean + 0.03
    print(f"     -> coherent (attractor): {'YES' if coherent else 'no'}  | "
          f"drifts (not an essence): {'YES' if drifts else 'no'}  | "
          f"souls individuate: {'YES' if distinct else 'no'}")

    self_ref = None
    if focal_lines and focal.self_model_history:
        own = focal.self_model_history[-1]
        other = next((a.self_model_history[-1] for a in w.agents[1:]
                      if a.self_model_history), "")
        to_own = statistics.fmean(score(l, own) for l in focal_lines)
        to_other = statistics.fmean(score(l, other) for l in focal_lines) if other else 0.0
        self_ref = to_own > to_other
        print(f"\n     SELF-REFERENCE  {focal.name}'s speech vs its OWN self-model: {to_own:+.3f}"
              f"   vs another's: {to_other:+.3f}")
        print(f"     -> speaks from its own self: {'YES' if self_ref else 'no'}")

    structural = coherent and drifts and distinct
    print("\n  VERDICT: " + (
        ("a SELF formed -- coherent yet drifting and individuated"
         + (", and spoken from." if self_ref else "; self-reference-in-speech weak (see above)."))
        if structural else
        "the self-model did not show the full signature (see measures above)."))


if __name__ == "__main__":
    main()
