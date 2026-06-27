"""Find the wheel regime where factions both FORM and PERSIST across rebirth.

experiment_churn proved the death->bardo->rebirth wheel, not the opinion space, is
what flattens live --world modularity: bardo dead-time fragments the live cohort and
reborn streams re-bond from zero faster than affinity accretes. So before tuning the
live viewer, sweep the wheel knobs (now World instance attrs) and measure, on the
real model, where modularity STAYS positive WHILE the wheel keeps turning (births>0).

Levers (per arm):
  life     lifespan range -- longer slows turnover, giving affinity time
  bardo    dissolution interval -- shorter keeps the live cohort from fragmenting
  vasana   perturbation on the carried lean -- lower = stronger transmission
  prebond  reborn_prebond: a stream born already bonded into its opinion-camp
           (the karmic-transmission lever; 0 = bond from scratch, as shipped)

Arms:
  fast        the shipped-ish churn baseline (expected: collapses to ~0)
  slow_life   longer lives, same wheel
  short_bardo souls return fast, live pop stays up
  prebond     reborn born into their camp + stronger transmission
  combo       short_bardo + prebond together

The metric that matters is PERSISTENCE: final modularity with births > 0. An arm that
holds modularity up while souls keep dying and re-coalescing is the regime where a
faction outlives its members -- the anatta/samsara payoff, measured.

Run:  python experiment_regime.py --llm ollama --model gemma3:1b --replicates 1
"""

from __future__ import annotations

import argparse
import random
import statistics
import time

from agent import belief as _belief
from agent import genesis as _genesis
from agent.agent import Agent
from services import factions
from services.llm import MockLLM, OllamaLLM
from world.sim import World

N_SOULS = 6
CHECKPOINTS = (30, 60, 90, 120)

ARMS = {
    "fast":        dict(life=(30, 55),  bardo=(20, 45), vasana=0.06, prebond=0.0),
    "slow_life":   dict(life=(90, 160), bardo=(20, 45), vasana=0.06, prebond=0.0),
    "short_bardo": dict(life=(30, 55),  bardo=(3, 10),  vasana=0.06, prebond=0.0),
    "prebond":     dict(life=(30, 55),  bardo=(20, 45), vasana=0.04, prebond=0.5),
    "combo":       dict(life=(35, 60),  bardo=(4, 12),  vasana=0.04, prebond=0.5),
}


def build(seed: int, cfg: dict, llm) -> World:
    world = World(rebirth_enabled=True)
    world.hearing_range = 1e12
    world.llm = llm
    world.bardo_ticks = cfg["bardo"]
    world.vasana_noise = cfg["vasana"]
    world.reborn_prebond = cfg["prebond"]
    rng = random.Random(seed)
    concepts = rng.sample(_genesis.SEED_CONCEPTS, N_SOULS)
    roles = rng.sample(_genesis.ROLES, N_SOULS)
    for i in range(N_SOULS):
        role, tasks = roles[i]
        text = f"{concepts[i]} {role} " + " ".join(tasks)
        temp = round(random.Random(seed * 7 + i).uniform(-1.0, 1.0), 2)
        life = rng.randint(*cfg["life"])
        a = Agent(f"s{i}", f"S{i}", (i * 20.0, 0.0), f"You are S{i}.",
                  _belief.tokens(text)[:8] or ["the days run together"],
                  llm, seed=seed + i + 1, temperament=temp, religion=None, lifespan=life)
        a.seed_opinion_text(text)
        world.add(a)
    return world


def run_one(seed: int, arm: str, make_llm, t0: float) -> dict:
    world = build(seed, ARMS[arm], make_llm(seed))
    traj, live = [], []
    last = 0
    for cp in CHECKPOINTS:
        world.run(cp - last)
        last = cp
        s = factions.summary(world.agents)
        traj.append(s["modularity"])
        live.append(s["n_agents"])
        print(f"[{time.time()-t0:6.0f}s] {arm:<11} seed={seed} t={cp:>3} -> "
              f"mod {s['modularity']:+.3f}, live {s['n_agents']}, blocs {s['n_blocs']}, "
              f"births {world._births}", flush=True)
    # persistence = final modularity, but only counts if the wheel actually turned
    return {"final": traj[-1], "min_after_births": min(traj[1:]) if len(traj) > 1 else traj[-1],
            "births": world._births, "mean_live": statistics.fmean(live)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=1)
    p.add_argument("--seed-base", type=int, default=500)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--arms", default=",".join(ARMS))
    args = p.parse_args()

    arms = [a for a in args.arms.split(",") if a in ARMS]
    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0, model=args.model) if args.model else OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)

    t0 = time.time()
    res = {}
    for arm in arms:
        rows = [run_one(s, arm, make_llm, t0) for s in seeds]
        res[arm] = {k: statistics.fmean(r[k] for r in rows) for k in rows[0]}

    print(f"\n=== Wheel regime sweep ({len(seeds)} reps, {CHECKPOINTS[-1]} ticks, "
          f"{args.llm}{'/'+args.model if args.model else ''}) ===")
    print(f"{'arm':<12}{'final mod':>11}{'births':>8}{'mean live':>11}  persists?")
    print("-" * 56)
    winners = []
    for arm in arms:
        r = res[arm]
        persists = r["final"] > 0.05 and r["births"] >= 1
        if persists:
            winners.append(arm)
        print(f"{arm:<12}{r['final']:>+11.3f}{r['births']:>8.1f}{r['mean_live']:>11.1f}"
              f"  {'YES' if persists else 'no'}")
    print("-" * 56)
    print("\n-> " + (
        f"factions PERSIST across the wheel in: {', '.join(winners)} -- that regime is the "
        "fix for live --world (a faction outliving its members)."
        if winners else
        "no arm holds factions through the wheel -- the turnover still outruns affinity; "
        "widen the sweep (even longer lives / stronger prebond / shorter bardo)."))


if __name__ == "__main__":
    main()
