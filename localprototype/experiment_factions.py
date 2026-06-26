"""Falsification harness for the central claim: 'agents form factions'.

A coherent two-sided debate proves nothing -- a good language model writes one
regardless of what the substrate is doing. So this harness ignores the prose and
measures the social graph, across SEEDED replicates, under three arms:

  full      faith on, social learning on        -- the system as shipped
  no_faith  no religions, social learning on     -- temperament-only baseline
  ablated   faith on, social learning OFF        -- the substrate frozen (null)

For each arm it reduces the final world to faction metrics (services/factions)
and reports mean +- std over seeds. The arms answer the questions the live demo
can't:

  * Does the 'ablated' arm collapse to ~0 modularity? If so, the metric detects
    ABSENCE of structure -- it isn't just always crying 'factions'. (control)
  * In 'full', is bloc_faith_purity ~1.0? Then the factions ARE the faith labels
    read back out -- homophily wired into hear(), not emergence.
  * Does 'no_faith' still cluster by temperament sign? Then 'belief' was never
    load-bearing; fixed temperament was.

Determinism: MockLLM + seeded agent RNGs, single-threaded, so every (seed, arm)
reproduces exactly. The affinity rule keys on the faith LABEL, not the spoken
words, so MockLLM's nonsense is a fair probe of the substrate. To exercise the
real model instead (slow), pass --llm ollama; it runs at temperature 0 so the
replicates stay reproducible.

Run:  python experiment_factions.py
      python experiment_factions.py --replicates 8 --ticks 150
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent.agent import Agent
from agent.religion import THE_DEVOUT, THE_PATH
from services import factions
from services.llm import MockLLM, OllamaLLM
from world.sim import World

# Mirror viewer.py's cast: faith is deliberately CROSSED with temperament (each
# faith spans cold and warm souls) so a bloc aligned with faith can be told apart
# from a bloc aligned with temperament -- the whole experiment hinges on that.
CAST = [
    ("river", "River", -0.55, "devout"),
    ("ash",   "Ash",   -0.6,  "path"),
    ("mire",  "Mire",  -0.5,  "devout"),
    ("lark",  "Lark",   0.6,  "path"),
    ("wren",  "Wren",   0.55, "devout"),
    ("sol",   "Sol",    0.5,  "path"),
]
RELIGION = {"devout": THE_DEVOUT, "path": THE_PATH}
# full/no_faith/ablated probe the LEGACY label-homophily substrate; 'emergent'
# is the new bounded-confidence opinion dynamics (no faith, mutable belief_vec).
ARMS = ("full", "no_faith", "ablated", "emergent")

# the metrics worth surfacing, in report order
KEYS = [
    "n_blocs", "modularity",
    "bloc_faith_purity", "bloc_temp_purity",
    "faith_affinity_gap", "temp_affinity_gap",
    "faith_in_hostility", "faith_cross_hostility",
]


# a generic stock of lines for the faithless arm (the faithful draw drift from
# their scripture instead). Without these MockLLM has nothing to compose from.
FALLBACK_PHRASES = ["the days run together", "something stirs in the quiet",
                    "i hold what i can", "the light shifts and is gone"]


def build(seed: int, arm: str, llm) -> World:
    """One deterministic world for an arm. The cohort is FIXED -- a huge lifespan
    and no breeding -- so the final state we measure is the same six souls that
    started, with their bonds accreted, not a fresh generation of heirs. Everyone
    is in earshot of everyone (hearing_range huge) so faction structure reflects
    affinity, not who drifted out of range."""
    world = World()                      # breed_enabled is False by default
    world.hearing_range = 1e12
    for i, (cid, name, temp, faith) in enumerate(CAST):
        # 'emergent' assigns NO faith -- bonding will come from the opinion vector
        relig = None if arm in ("no_faith", "emergent") else RELIGION[faith]
        a = Agent(cid, name, (i * 20.0, 0.0), f"You are {name}.", FALLBACK_PHRASES,
                  llm, seed=seed + i + 1, temperament=temp, religion=relig,
                  lifespan=10 ** 9)     # no death during the run -> stable cohort
        if arm == "ablated":
            a.social_learning = False   # freeze the social graph
        if arm == "emergent":
            # seed the opinion from an RNG keyed on (seed, agent) but DELIBERATELY
            # independent of temperament/faith, so any cluster that forms cannot
            # be a fixed label read back out. Different seeds -> different starts.
            a.seed_opinion(random.Random(seed * 1000 + i))
        world.add(a)
    return world


def run_one(seed: int, arm: str, ticks: int, make_llm) -> tuple[dict, dict]:
    """Run one replicate to its final state; return (faction metrics, bloc
    partition). The partition is kept so co-membership can be compared ACROSS
    seeds -- the test for history-dependence."""
    world = build(seed, arm, make_llm(seed))
    world.run(ticks)
    return factions.summary(world.agents), factions.partition(world.agents)


def aggregate(rows: list[dict]) -> dict:
    """mean and std across replicates for each metric."""
    out = {}
    for k in KEYS:
        vals = [r[k] for r in rows]
        out[k] = (statistics.fmean(vals),
                  statistics.stdev(vals) if len(vals) > 1 else 0.0)
    return out


def _fmt(stat: tuple[float, float]) -> str:
    m, s = stat
    return f"{m:+.3f}±{s:.3f}"


def report(results: dict[str, dict], comemb: dict[str, float],
           seeds: list[int], ticks: int) -> str:
    lines = [
        "\n=== Faction falsification: arm comparison ===",
        f"replicates={len(seeds)}  ticks={ticks}  seeds {seeds[0]}..{seeds[-1]}  "
        "(MockLLM, deterministic)\n",
    ]
    width = 22
    header = "metric".ljust(width) + "".join(a.ljust(13) for a in ARMS)
    lines.append(header)
    lines.append("-" * len(header))
    for k in KEYS:
        row = k.ljust(width) + "".join(_fmt(results[a][k]).ljust(13) for a in ARMS)
        lines.append(row)
    # cross-seed metric: not a per-run mean, so it sits below the table
    lines.append("comemb_variance".ljust(width)
                 + "".join(f"{comemb[a]:.3f}".ljust(13) for a in ARMS))

    # automated read-out: the experiment states its own verdict
    full, no_faith = results["full"], results["no_faith"]
    ablated, emergent = results["ablated"], results["emergent"]
    lines.append("\n--- read-out ---")
    abl_mod = ablated["modularity"][0]
    lines.append(
        f"* control: ablated modularity = {abl_mod:+.3f} -> "
        + ("PASS, the metric collapses to ~0 with the substrate frozen, so it is "
           "detecting real structure, not always crying 'factions'." if abs(abl_mod) < 0.02
           else "WARNING, ablated arm still shows structure; the metric is suspect."))
    fp = full["bloc_faith_purity"][0]
    lines.append(
        f"* full (legacy): bloc_faith_purity = {fp:.3f}, comemb_variance = "
        f"{comemb['full']:.3f} -> "
        + ("the blocs ARE the faith labels and membership never varies by seed -- "
           "deterministic homophily, NOT emergence." if fp > 0.9 and comemb['full'] < 0.02
           else "structure faith doesn't fully explain."))

    # the headline: did the emergent arm actually emerge?
    em_mod = emergent["modularity"][0]
    em_tp = emergent["bloc_temp_purity"][0]
    em_var = comemb["emergent"]
    forms = em_mod > 0.05
    not_label = em_tp < 0.95
    history = em_var > 0.02
    lines.append(
        f"* EMERGENT arm: modularity = {em_mod:+.3f}, bloc_temp_purity = {em_tp:.3f}, "
        f"comemb_variance = {em_var:.3f}")
    if forms and not_label and history:
        lines.append(
            "  -> EMERGENCE CONFIRMED: clusters form (modularity > 0), they do NOT "
            "reduce to the fixed temperament label (purity < 1), and WHICH souls "
            "ally depends on run history (variance > 0). No assigned label predicts "
            "the factions -- they arose from the opinion dynamics.")
    else:
        reasons = []
        if not forms:
            reasons.append("no clusters formed (CONFIDENCE too high -> isolation, "
                           "or too low -> one consensus blob; tune the phase knob)")
        if forms and not not_label:
            reasons.append("clusters still align with temperament (purity ~1)")
        if forms and not history:
            reasons.append("membership is seed-invariant (not history-dependent)")
        lines.append("  -> NOT YET EMERGENT: " + "; ".join(reasons) + ".")

    lines.append(
        "\nThis harness is the gate: a faction feature counts as emergent only when "
        "the EMERGENT-arm signature holds and the ablated control stays at ~0.")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=6)
    p.add_argument("--ticks", type=int, default=120)
    p.add_argument("--seed-base", type=int, default=200)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock",
                   help="mock = deterministic substrate probe; ollama = real model at temp 0")
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0)   # temp 0 so replicates reproduce
        make_llm = lambda _seed: shared
    else:
        make_llm = lambda seed: MockLLM(seed=seed)

    results, comemb = {}, {}
    for arm in ARMS:
        runs = [run_one(s, arm, args.ticks, make_llm) for s in seeds]
        results[arm] = aggregate([r[0] for r in runs])
        comemb[arm] = factions.comembership_variance([r[1] for r in runs])
    print(report(results, comemb, seeds, args.ticks))


if __name__ == "__main__":
    main()
