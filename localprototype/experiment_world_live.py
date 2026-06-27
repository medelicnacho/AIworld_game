"""End-to-end check: does the 'combo' wheel regime make factions PERSIST in the
ACTUAL --world pipeline -- genesis-authored souls + concept voice -- not just the
bare trade-text souls of experiment_regime?

experiment_regime proved the wheel MECHANISM on simple souls (1b). --world adds two
things that change SPEECH (and thus how belief_vec/stance get grounded): souls are
authored by the LLM with life-stories (agent.genesis), and they speak in concept
voice (interpret their Markov drift). This runs the real soul pipeline headlessly,
with short lifespans so the wheel turns inside the budget, and compares:

  plain  rebirth ON, shipped wheel defaults           -- expected to collapse to ~0
  combo  rebirth ON, the tuned regime (as in viewer)  -- expected to persist

Same authored souls per seed. If combo holds modularity up through the rebirths
while plain collapses, the viewer tuning is confirmed on the genuine --world voice.

Run:  python experiment_world_live.py --llm ollama --model gemma3:1b
"""

from __future__ import annotations

import argparse
import random
import statistics
import time

from agent import genesis as _genesis
from agent.agent import Agent
from services import factions
from services.llm import MockLLM, OllamaLLM
from world.sim import World

N_SOULS = 6
CHECKPOINTS = (30, 60, 90, 120)
VOICE = "concept"   # set from --voice; "concept" is the --world default, "normal" = plain persona


def build(seed: int, arm: str, llm, engine: str = "stance") -> World:
    """The real --world soul pipeline: each soul AUTHORED by the LLM (genesis) and
    voiced in concept mode. Short lifespans so the wheel turns headlessly. `combo`
    applies the viewer's tuned wheel; `plain` leaves the shipped defaults."""
    world = World(rebirth_enabled=True)
    world.hearing_range = 1e12
    world.llm = llm
    if arm == "combo":
        world.reborn_prebond = 0.5
        world.vasana_noise = 0.04
        world.bardo_ticks = (8, 20)
    rng = random.Random(seed)
    concepts = rng.sample(_genesis.SEED_CONCEPTS, N_SOULS)
    chars = [_genesis.generate_character(llm, rng, concepts[i]) for i in range(N_SOULS)]
    _genesis.dedupe_names(chars, rng)
    for i, ch in enumerate(chars):
        life = rng.randint(30, 55)   # turn the wheel inside the run
        a = Agent(f"s{i}", ch.name, (i * 20.0, 0.0), "", [], llm,
                  seed=seed + i + 1, lifespan=life, religion=None)
        _genesis.seed_agent(a, ch)       # name/story/Markov/opinion/stance
        if engine == "belief":
            a.stance_vec = None          # bond on the LEXICAL belief_vec, not stance
        a.concept_speech = (VOICE == "concept")   # --world voice, or plain persona speech
        world.add(a)
    return world


def run_one(seed: int, arm: str, make_llm, t0: float, engine: str = "stance") -> dict:
    world = build(seed, arm, make_llm(seed), engine)
    traj, live = [], []
    last = 0
    for cp in CHECKPOINTS:
        world.run(cp - last)
        last = cp
        s = factions.summary(world.agents)
        traj.append(s["modularity"])
        live.append(s["n_agents"])
        print(f"[{time.time()-t0:6.0f}s] {arm:<6} seed={seed} t={cp:>3} -> "
              f"mod {s['modularity']:+.3f}, live {s['n_agents']}, blocs {s['n_blocs']}, "
              f"births {world._births}", flush=True)
    return {"final": traj[-1], "births": world._births, "mean_live": statistics.fmean(live)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=1)
    p.add_argument("--seed-base", type=int, default=600)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--engine", choices=["stance", "belief"], default="stance",
                   help="which vector drives bonding: stance_vec (as shipped) or the lexical belief_vec")
    p.add_argument("--arms", default="plain,combo")
    p.add_argument("--voice", choices=["concept", "normal"], default="concept",
                   help="concept = the --world interpreted-drift voice; normal = plain persona speech")
    args = p.parse_args()
    global VOICE
    VOICE = args.voice

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0, model=args.model) if args.model else OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)

    arms = [a for a in args.arms.split(",") if a in ("plain", "combo")]
    t0 = time.time()
    res = {}
    for arm in arms:
        rows = [run_one(s, arm, make_llm, t0, args.engine) for s in seeds]
        res[arm] = {k: statistics.fmean(r[k] for r in rows) for k in rows[0]}

    print(f"\n=== --world live regime check (genesis, {args.voice} voice, engine={args.engine}, "
          f"{len(seeds)} reps, {CHECKPOINTS[-1]} ticks, {args.llm}{'/'+args.model if args.model else ''}) ===")
    for arm in arms:
        r = res[arm]
        print(f"  {arm:<6} final modularity {r['final']:+.3f}   births {r['births']:.1f}   "
              f"mean live {r['mean_live']:.1f}")
    holds = res["combo"]["final"] > 0.05 and res["combo"]["births"] >= 1
    print("\n-> " + (
        "CONFIRMED on the real --world voice: combo holds factions through the wheel "
        "where plain rebirth does not. The viewer tuning works end-to-end."
        if holds and res["combo"]["final"] > res["plain"]["final"] else
        "combo did NOT hold on the genesis+concept pipeline -- the authored/concept "
        "speech grounds differently than bare trade-text; re-tune on this voice."))


if __name__ == "__main__":
    main()
