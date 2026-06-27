"""Is the rebirth WHEEL what collapses live --world modularity to ~0?

The real-model harness (experiment_grounded --llm ollama) showed the GROUNDED lexical
engine forms factions fine on a STABLE cohort (modularity +0.34 on gemma3:1b) -- so
the "grounded space is starved / orthogonal" story was a MockLLM artifact (MockLLM's
echoey speech collapses everyone into one blob; real diverse trade-speech grounds the
vectors apart). Yet live --world sits at modularity ~0.

The one thing live --world has that the stable harness lacks is the death -> bardo ->
rebirth WHEEL. This isolates it: identical souls, identical engine, identical ticks,
toggling ONLY rebirth (with short lifespans so the wheel actually turns inside the
run). Modularity is sampled at checkpoints so you can watch the stable cohort CLIMB
while the churning one stays flat.

  stable  rebirth OFF, immortal cohort   -- affinity has time to accumulate
  churn   rebirth ON,  short lifespans   -- membership shredded as fast as it accretes

If stable forms factions and churn collapses to ~0, the wheel is the cause, and the
lever for live --world is there (slower wheel / longer lives / stronger vasana
transmission), NOT in the opinion space. Real model: --llm ollama (slow); MockLLM is
only a plumbing check (it can't form grounded factions, see above).

Run:  python experiment_churn.py --llm ollama --model gemma3:1b --replicates 2
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

ARMS = ("stable", "churn")
N_SOULS = 6
CHECKPOINTS = (30, 60, 90, 120)


def build(seed: int, arm: str, llm) -> World:
    """Identical grounded souls for both arms; the ONLY difference is rebirth +
    lifespan. world.llm is set so the bardo can coalesce reborn streams."""
    world = World(rebirth_enabled=(arm == "churn"))
    world.hearing_range = 1e12
    world.llm = llm
    rng = random.Random(seed)
    concepts = rng.sample(_genesis.SEED_CONCEPTS, N_SOULS)
    roles = rng.sample(_genesis.ROLES, N_SOULS)
    for i in range(N_SOULS):
        role, tasks = roles[i]
        text = f"{concepts[i]} {role} " + " ".join(tasks)
        temp = round(random.Random(seed * 7 + i).uniform(-1.0, 1.0), 2)
        # stable: effectively immortal. churn: short lives so the wheel turns inside
        # the run (and bardo dead-time keeps splitting the live cohort).
        life = 10 ** 9 if arm == "stable" else rng.randint(30, 55)
        a = Agent(f"s{i}", f"S{i}", (i * 20.0, 0.0), f"You are S{i}.",
                  _belief.tokens(text)[:8] or ["the days run together"],
                  llm, seed=seed + i + 1, temperament=temp, religion=None, lifespan=life)
        a.seed_opinion_text(text)
        world.add(a)
    return world


def run_one(seed: int, arm: str, make_llm, t0: float) -> list[tuple]:
    world = build(seed, arm, make_llm(seed))
    snaps, last = [], 0
    for cp in CHECKPOINTS:
        world.run(cp - last)
        last = cp
        s = factions.summary(world.agents)
        snaps.append((cp, s["modularity"], s["n_agents"], s["n_blocs"]))
        print(f"[{time.time()-t0:6.0f}s] arm={arm:<6} seed={seed} tick={cp:>3} -> "
              f"modularity {s['modularity']:+.3f}, live {s['n_agents']}, blocs {s['n_blocs']}, "
              f"births {world._births}", flush=True)
    return snaps


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=2)
    p.add_argument("--seed-base", type=int, default=400)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0, model=args.model) if args.model else OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)

    t0 = time.time()
    final = {arm: [] for arm in ARMS}
    for arm in ARMS:
        for s in seeds:
            snaps = run_one(s, arm, make_llm, t0)
            final[arm].append(snaps[-1][1])   # modularity at the last checkpoint

    print(f"\n=== Churn isolation: rebirth ON vs OFF, same souls/engine "
          f"({len(seeds)} reps, {CHECKPOINTS[-1]} ticks, {args.llm}"
          f"{'/'+args.model if args.model else ''}) ===")
    sm = statistics.fmean(final["stable"])
    cm = statistics.fmean(final["churn"])
    print(f"  stable  final modularity: {sm:+.3f}   (per-rep {', '.join(f'{x:+.3f}' for x in final['stable'])})")
    print(f"  churn   final modularity: {cm:+.3f}   (per-rep {', '.join(f'{x:+.3f}' for x in final['churn'])})")
    print("\n-> " + (
        "WHEEL CONFIRMED as the cause: the stable cohort forms factions while the "
        "churning one collapses toward ~0 -- live --world's flat modularity is the "
        "rebirth turnover outrunning affinity, not the opinion space."
        if sm > 0.05 and cm < sm * 0.5 else
        "NOT the (whole) story: churn modularity is comparable to stable -- the wheel "
        "is not what flattens it; look elsewhere (concept voice, range, genesis)."))


if __name__ == "__main__":
    main()
