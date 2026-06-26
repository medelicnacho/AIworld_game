"""Text-confound experiment: does the substrate change what is SAID, or only get
narrated over?

The faction harness proved the substrate shapes the social GRAPH. This asks the
harder question the review raised: does it shape the spoken OUTPUT? The faith
system feeds belief / challenge / hostility / relationship into every speech
prompt -- but if the agents say essentially the same things whether or not that
machinery is live, then it is decorative for the transcript: the LLM is doing the
talking and ignoring the social state handed to it.

Method -- same seed, two conditions:
  full     substrate on (affinity/hostility/belief update, prompt reflects them)
  ablated  social_learning off (the graph is frozen; those prompt fields stay inert)
Collect each run's transcript and measure how far the two VOCABULARIES drift
apart. Compare that SUBSTRATE EFFECT against a NOISE FLOOR -- the drift between two
runs that differ only by seed, same condition. The verdict:

  substrate_effect <= noise_floor  ->  the substrate adds nothing to what's said
  substrate_effect >  noise_floor  ->  the substrate genuinely shapes speech

MockLLM ignores the prompt's social fields, so on MockLLM the substrate effect is
~0 by construction -- this default run is a PLUMBING check, not the real result.
The real test needs a model that reads its prompt: run --llm ollama (temperature 0
for reproducibility; slow, so keep ticks/replicates small).

Run:  python experiment_confound.py                       # mock plumbing check
      python experiment_confound.py --llm ollama --replicates 3 --ticks 40
"""

from __future__ import annotations

import argparse
import statistics

from agent import belief
from agent.agent import _cosine, _normalize
from services.llm import MockLLM, OllamaLLM
from experiment_factions import build


def transcript(seed: int, ablated: bool, ticks: int, llm) -> list[str]:
    """Run one faith world; return everything spoken, in order."""
    world = build(seed, "full", llm)
    if ablated:
        for a in world.agents:
            a.social_learning = False   # freeze the social graph -> inert prompt fields
    said: list[str] = []
    world.bus.subscribe("utterance", lambda u: said.append(u.text))
    world.run(ticks)
    return said


def divergence(t1: list[str], t2: list[str]) -> float:
    """How far apart two transcripts' vocabularies are: 1 - cosine of their
    bag-of-words. 0 = identical wording, 1 = no shared salient vocabulary."""
    v1 = _normalize(belief.text_to_opinion(" ".join(t1)))
    v2 = _normalize(belief.text_to_opinion(" ".join(t2)))
    return 1.0 - _cosine(v1, v2)


def compare(seeds: list[int], ticks: int, make_llm) -> dict:
    full = {s: transcript(s, False, ticks, make_llm(s)) for s in seeds}
    ablated = {s: transcript(s, True, ticks, make_llm(s)) for s in seeds}
    # substrate effect: same seed, on vs off
    effect = [divergence(full[s], ablated[s]) for s in seeds]
    # noise floor: different seeds, same (full) condition -- the drift that is just
    # run-to-run variation, the bar the substrate effect has to clear to matter
    floor = [divergence(full[a], full[b]) for a, b in zip(seeds, seeds[1:])]
    return {
        "effect_mean": statistics.fmean(effect),
        "effect_std": statistics.pstdev(effect) if len(effect) > 1 else 0.0,
        "floor_mean": statistics.fmean(floor) if floor else 0.0,
        "floor_std": statistics.pstdev(floor) if len(floor) > 1 else 0.0,
        "lines_full": statistics.fmean(len(full[s]) for s in seeds),
    }


def report(r: dict, seeds: list[int], ticks: int, backend: str) -> str:
    matters = r["effect_mean"] > r["floor_mean"] + r["floor_std"]
    lines = [
        "\n=== Text-confound: does the substrate change what is SAID? ===",
        f"replicates={len(seeds)}  ticks={ticks}  backend={backend}  "
        f"(~{r['lines_full']:.0f} lines/run)\n",
        f"  substrate effect (full vs ablated, same seed): {r['effect_mean']:.3f} ± {r['effect_std']:.3f}",
        f"  noise floor      (full vs full, diff seed):    {r['floor_mean']:.3f} ± {r['floor_std']:.3f}\n",
    ]
    if matters:
        lines.append("-> ABOVE the noise floor: the substrate measurably changes the "
                     "spoken output -- belief/hostility/relationship are not just "
                     "narrated, they reshape what is said.")
    else:
        lines.append("-> AT the noise floor: the substrate does NOT change the spoken "
                     "output beyond run-to-run noise. On MockLLM this is expected (it "
                     "ignores the prompt's social fields). On a real model it would "
                     "mean the ideology machinery is decorative for the transcript.")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=4)
    p.add_argument("--ticks", type=int, default=60)
    p.add_argument("--seed-base", type=int, default=300)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)
    print(report(compare(seeds, args.ticks, make_llm), seeds, args.ticks, args.llm))


if __name__ == "__main__":
    main()
