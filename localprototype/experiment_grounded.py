"""Baseline: does the GROUNDED lexical opinion engine -- the one --world actually
runs -- support factions, or is it starved?

experiment_factions.py's 'emergent' arm uses ABSTRACT seed_opinion (6-dim random
gaussian vectors), which start with large mutual overlap (cosine ~ +-0.4) and so
cluster readily -- modularity ~ +0.29, "EMERGENCE CONFIRMED". But --world does not
run that space. It runs seed_opinion_text: a 128-dim LEXICAL hash grounded in each
soul's words. And since the jobs fix gave every soul a DISTINCT trade vocabulary,
those grounded vectors start near-ORTHOGONAL -- there is almost nothing to bond on.

This harness measures the gap directly, with rebirth OFF and a stable cohort, so
the result is the engine's own doing, not the churn of the wheel:

  abstract  -- seed_opinion (the space the existing harness blesses)
  grounded  -- seed_opinion_text over trade-distinct souls (the space --world runs)

For each it reports the INITIAL pairwise cosine (how much signal the engine has to
work with) and the FINAL faction metrics. The point it makes: the grounded arm's
opinion space is so sparse that modularity collapses regardless of how cleanly the
abstract arm clusters. That is WHY live --world sits at modularity ~0.

MockLLM here is deliberately OPTIMISTIC: its speak() echoes the prior speaker, so
grounding-from-speech manufactures shared vocabulary the real model would not. If
even this inflated run shows the grounded arm starved, ollama (distinct authored
speech) is worse. The real number: --llm ollama (slow). This file is also the
regression gate for the stance-affinity fix: after it, the grounded arm's
modularity should rise while comemb_variance stays > 0.

Run:  python experiment_grounded.py
      python experiment_grounded.py --replicates 8 --ticks 150
"""

from __future__ import annotations

import argparse
import math
import random
import statistics

from agent import belief as _belief
from agent import genesis as _genesis
from agent.agent import Agent
from services import factions
from services.llm import MockLLM, OllamaLLM
from world.sim import World

ARMS = ("abstract", "grounded")
KEYS = ["n_blocs", "modularity", "bloc_temp_purity", "temp_affinity_gap"]
N_SOULS = 6


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _grounding_text(rng: random.Random) -> tuple[str, float]:
    """A trade-distinct grounding line faithful to --world genesis: a soul's
    preoccupation + its trade's concrete tasks (the distinct vocabulary). Returns
    (text, temperament). Real authored lines are MORE trade-specific, so this
    overestimates overlap -- a conservative test."""
    concept = rng.choice(_genesis.SEED_CONCEPTS)
    role, tasks = rng.choice(_genesis.ROLES)
    return f"{concept} {role} " + " ".join(tasks), round(rng.uniform(-1.0, 1.0), 2)


def build(seed: int, arm: str, llm) -> tuple[World, list[list[float]]]:
    """A stable cohort (no death, no breeding, all in earshot) for one arm.
    Returns the world and the souls' INITIAL belief_vecs (to measure starting
    signal before any interaction moves them)."""
    world = World()
    world.hearing_range = 1e12
    rng = random.Random(seed)
    # sample distinct trades/concepts per world, as genesis does
    concepts = rng.sample(_genesis.SEED_CONCEPTS, N_SOULS)
    roles = rng.sample(_genesis.ROLES, N_SOULS)
    init_vecs: list[list[float]] = []
    for i in range(N_SOULS):
        role, tasks = roles[i]
        text = f"{concepts[i]} {role} " + " ".join(tasks)
        temp = round(random.Random(seed * 7 + i).uniform(-1.0, 1.0), 2)
        a = Agent(f"s{i}", f"S{i}", (i * 20.0, 0.0), f"You are S{i}.",
                  _belief.tokens(text)[:8] or ["the days run together"],
                  llm, seed=seed + i + 1, temperament=temp, religion=None,
                  lifespan=10 ** 9)
        if arm == "grounded":
            a.seed_opinion_text(text)            # the space --world runs
        else:
            a.seed_opinion(random.Random(seed * 1000 + i))  # abstract 6-dim
        init_vecs.append(list(a.belief_vec))
        world.add(a)
    return world, init_vecs


def _cos_stats(vecs: list[list[float]]) -> dict:
    cs = [_cos(vecs[i], vecs[j]) for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
    above = sum(1 for c in cs if c >= 0.1)   # the live CONFIDENCE engagement bar
    return {"cos_mean": statistics.fmean(cs), "cos_abs_mean": statistics.fmean(abs(c) for c in cs),
            "frac_engaged": above / len(cs)}


def run_one(seed: int, arm: str, ticks: int, make_llm):
    world, init_vecs = build(seed, arm, make_llm(seed))
    cs = _cos_stats(init_vecs)
    world.run(ticks)
    return factions.summary(world.agents), factions.partition(world.agents), cs


def aggregate(rows, cstats) -> dict:
    out = {}
    for k in KEYS:
        vals = [r[k] for r in rows]
        out[k] = (statistics.fmean(vals), statistics.stdev(vals) if len(vals) > 1 else 0.0)
    for k in ("cos_mean", "cos_abs_mean", "frac_engaged"):
        vals = [c[k] for c in cstats]
        out[k] = (statistics.fmean(vals), statistics.stdev(vals) if len(vals) > 1 else 0.0)
    return out


def _fmt(stat) -> str:
    return f"{stat[0]:+.3f}±{stat[1]:.3f}"


def report(results, comemb, seeds, ticks) -> str:
    rows = KEYS + ["cos_mean", "cos_abs_mean", "frac_engaged"]
    width = 18
    lines = ["\n=== Grounded vs abstract opinion engine (rebirth OFF, stable cohort) ===",
             f"replicates={len(seeds)}  ticks={ticks}  seeds {seeds[0]}..{seeds[-1]}\n",
             "metric".ljust(width) + "".join(a.ljust(15) for a in ARMS),
             "-" * (width + 15 * len(ARMS))]
    for k in rows:
        lines.append(k.ljust(width) + "".join(_fmt(results[a][k]).ljust(15) for a in ARMS))
    lines.append("comemb_variance".ljust(width)
                 + "".join(f"{comemb[a]:.3f}".ljust(15) for a in ARMS))

    ab, gr = results["abstract"], results["grounded"]
    lines.append("\n--- read-out ---")
    lines.append(f"* abstract start: |cos| {ab['cos_abs_mean'][0]:.3f}, "
                 f"{100*ab['frac_engaged'][0]:.0f}% of pairs above CONFIDENCE -> modularity "
                 f"{ab['modularity'][0]:+.3f} (the space the harness blesses).")
    lines.append(f"* grounded start: |cos| {gr['cos_abs_mean'][0]:.3f}, "
                 f"{100*gr['frac_engaged'][0]:.0f}% of pairs above CONFIDENCE -> modularity "
                 f"{gr['modularity'][0]:+.3f} (the space --world runs).")
    starved = gr["modularity"][0] < 0.05
    lines.append("  -> " + (
        "GROUNDED SPACE STARVED: trade-distinct souls start near-orthogonal, so the "
        "opinion engine has almost nothing to bond on and no factions form -- this is "
        "why live --world sits at modularity ~0. The signed-stance fix targets exactly "
        "this." if starved else
        "grounded arm forms structure -- the stance fix may already be unnecessary, recheck."))
    lines.append("\n(MockLLM is optimistic here: its echoey speech manufactures shared vocab. "
                 "The real, worse number needs --llm ollama.)")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=6)
    p.add_argument("--ticks", type=int, default=120)
    p.add_argument("--seed-base", type=int, default=300)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)

    results, comemb = {}, {}
    for arm in ARMS:
        runs = [run_one(s, arm, args.ticks, make_llm) for s in seeds]
        results[arm] = aggregate([r[0] for r in runs], [r[2] for r in runs])
        comemb[arm] = factions.comembership_variance([r[1] for r in runs])
    print(report(results, comemb, seeds, args.ticks))


if __name__ == "__main__":
    main()
