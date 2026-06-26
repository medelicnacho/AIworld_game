"""How load-bearing is the Markov subconscious? Does the LLM's speech actually
track the drift it's fed -- and how much does that depend on the mode?

For each of several distinct drift themes we generate a line, then score (via nomic
embeddings) how close the line lands to ITS OWN drift versus to a DIFFERENT drift:

  effect = mean[ sim(output_i, theme_i) - sim(output_(i+1), theme_i) ]

A high effect means the output is driven by the drift it was given (the Markov is
load-bearing); ~0 means the drift barely moves the output (the persona/scaffolding
is doing the steering). We run it in all three speech modes to compare:

  persona  -- the default: 'Drifting through: ...' buried in a full persona prompt
  raw      -- the drift IS the prompt, voiced verbatim
  concept  -- the drift IS the prompt, interpreted into meaning

Needs ollama (gemma3:4b speech + nomic-embed-text scoring).

Run:  python experiment_drift_voice.py
"""

from __future__ import annotations

import argparse
import statistics

from services import embed
from services.llm import OllamaLLM, SpeechContext

# distinct, evocative fragment-sets, the kind a Markov chain emits
THEMES = [
    ["cold water remembers", "the deep holds what falls", "salt and old metal"],
    ["the orchard in bloom", "hands deep in warm soil", "bread cooling on the sill"],
    ["the machine hums below", "gears and pressure and weight", "precise cold logic"],
    ["the hunt at first light", "tracks in the frost", "the wolf's long cry"],
    ["the sea takes the village", "nets heavy with the drowned", "the tide never asks"],
    ["dawn over the hills", "the dread of waking", "a dream already fading"],
]
MODES = {"persona": {}, "raw": {"raw_mind": True}, "concept": {"concept_mind": True}}


def _ctx(drift, **mode):
    return SpeechContext(name="River", persona="a wandering soul who speaks your own mind.",
                         mood=0.0, drift=list(drift), **mode)


def measure(llm, mode_kw: dict, samples: int) -> float:
    """Mean (own-drift similarity - other-drift similarity) across the themes."""
    outs = []
    for theme in THEMES:
        lines = [llm.speak(_ctx(theme, **mode_kw)) for _ in range(samples)]
        outs.append(" ".join(lines))
    own, other = [], []
    n = len(THEMES)
    for i, theme in enumerate(THEMES):
        target = " ".join(theme)
        own.append(embed.score(outs[i], target))            # output vs its OWN drift
        other.append(embed.score(outs[(i + 1) % n], target))  # a different output vs this drift
    return statistics.fmean(own) - statistics.fmean(other)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=1)
    args = p.parse_args()
    llm = OllamaLLM(temperature=0.9)
    print("\n=== How load-bearing is the Markov drift, by mode? ===")
    print("effect = output's similarity to its OWN drift minus to a DIFFERENT drift\n")
    for name, kw in MODES.items():
        eff = measure(llm, kw, args.samples)
        print(f"  {name:9} drift-influence effect: {eff:+.3f}")


if __name__ == "__main__":
    main()
