"""THE WAR FALSIFIER: do raids EMERGE from scarcity, and do feuds OUTLIVE their founders?

War (world/war.py) is only worth having if it is caused, not decorative. Two
pre-registered claims, the ecology's headline gates:

  G1 WARS COME FROM WANT-BESIDE-PLENTY : raids need hunger FACING a fat granary.
      Tuning re-taught the house lesson (the graded-scarcity band, now for war):
      UNIFORM poverty raids nothing -- there is no target worth marching for. The arms
      are therefore UNEQUAL (lean seasons gnaw the crag beside a still-fat vale) vs
      FED-FOR-ALL (yields so kind that no bloc ever drops below the hunger line).
      Claim: unequal-arm raids >= 2x fed-arm pooled, and every seed unequal >= fed.
  G2 THE FEUD OUTLIVES ITS FOUNDERS : run a scarce world long past full generational
      turnover; the land-keyed grievance (feud:X>Y) is still carried by souls, NONE of
      whom fought the raid that started it. A war that outlives everyone who began it --
      the churn test (§ lore), applied to hatred.

Protocol (substrate-only, MockLLM, deterministic): a 24-soul ecology, two opinion blocs
on two grounds, heredity + selection + war on, rebirth off (lineages END). SCARCE =
soils biting + short hardship interval; ABUNDANT = fat soils, rare hardship. G1 pooled
over the tuning/verdict seeds; G2 per seed.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 231-235; G1 pooled ratio >= 2x
and every held-out seed scarce>=abundant; G2 >= 4/5).

  python experiment_war.py
"""
from __future__ import annotations

import random
import sys

from agent.agent import Agent
from agent.bond import Bond
from agent.genome import express, from_agent
from services import embed
from world import regions as R
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (231, 232, 233, 234, 235)
N = 24


def build(seed: int, scarce: bool) -> World:
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=seed)
    w.llm = __import__("services.llm", fromlist=["MockLLM"]).MockLLM(seed=7)
    w.stakes_enabled = True
    w.regions_enabled = True
    w.regions = R.Regions(seed=seed)
    w.war_enabled = True
    w.heredity_enabled = True
    w.selection_enabled = True
    w.commons_first = True
    w.lore_enabled = True          # G2: the feud must be RETELLABLE to reach the unborn
    w.murmur_enabled = True
    w.clock_enabled = True         # and KEEPABLE: elders' lore-salience floor is what
                                   # lets a story outlive its tellers (5.16's
                                   # legend-keepers) -- the live ecology runs clocked too
    w.move_enabled = False                        # hold the geography fixed: the two
    w.bounds = (900.0, 600.0)                      # blocs stay on their two grounds
    w.max_souls = N + 20
    w.hardship_interval = 60 if scarce else 400
    w.yield_scale = 1.0 if scarce else 2.5     # unequal: winters bite the crag beside a
                                               # fat vale; fed: no one ever goes hungry
    rich = max(range(6), key=lambda i: w.regions.yields[i])
    poor = min(range(6), key=lambda i: w.regions.yields[i])
    cx = lambda i: ((i % R.COLS) * 300 + 150.0, (i // R.COLS) * 300 + 150.0)
    crew = {rich: [], poor: []}
    for i in range(N):
        home = poor if i < N // 2 else rich
        a = Agent(f"s{i}", f"F{i}", cx(home), "You are a soul.", ["the well"],
                  w.llm, seed=1000 * seed + i, temperament=0.0, lifespan=rng.randint(120, 220))
        a.bond_enabled = True
        a.boldness = rng.uniform(0.5, 0.95)        # a martial founding stock
        a.metabolism = rng.uniform(0.3, 0.7)
        a.genome = from_agent(a, rng)
        express(a.genome, a)
        a.belief_vec = ((1.0, 0, 0, 0, 0, 0) if home == poor else (-1.0, 0, 0, 0, 0, 0))
        w.add(a)
        crew[home].append(a)
    for grp in crew.values():                      # deep in-bloc trust -> real parties
        for a in grp:
            for b in grp:
                if a is not b:
                    a.bonds[b.id] = Bond(trust=0.8, history=2.5)
    w.regions.pools = [6.0 if scarce else 15.0] * 6
    return w


def run(seed: int, scarce: bool, ticks: int = 1500) -> dict:
    w = build(seed, scarce)
    raids = 0
    w.bus.subscribe("raid", lambda p: None)
    founders = {a.id for a in w.agents}
    for _ in range(ticks):
        with w.lock:
            w.step(speak=True)     # souls retell; a land-keyed feud can reach newborns
    raids = len(w._war_log)
    # G2: is any feud-grievance still carried, by souls who did NOT fight it?
    feud_alive = False
    for a in w.agents:
        for m in a.memory.items:
            if isinstance(m.lore_id, str) and m.lore_id.startswith("feud:"):
                if a.id not in founders:            # a soul born AFTER the founding
                    feud_alive = True
    turnover = 1.0 - len(founders & {a.id for a in w.agents}) / max(1, len(founders))
    return {"raids": raids, "feud_alive": feud_alive, "turnover": turnover,
            "alive": len(w.agents)}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        sc = run(seed, scarce=True)
        ab = run(seed, scarce=False)
        rows.append({"scarce_raids": sc["raids"], "abundant_raids": ab["raids"],
                     "g1": sc["raids"] >= ab["raids"], "g2": sc["feud_alive"],
                     "turnover": sc["turnover"]})
        print(f"seed {seed}: scarce {sc['raids']} raids vs abundant {ab['raids']} | "
              f"feud outlives founders {sc['feud_alive']} "
              f"(turnover {sc['turnover']:.0%}) | "
              f"G1 {'PASS' if rows[-1]['g1'] else 'FAIL'}  "
              f"G2 {'PASS' if rows[-1]['g2'] else 'FAIL'}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 231-235 (the verdict)")
    tot_sc = sum(r["scarce_raids"] for r in held)
    tot_ab = sum(r["abundant_raids"] for r in held)
    ratio = tot_sc / max(1, tot_ab)
    g1 = ratio >= 2.0 and all(r["g1"] for r in held)
    g2 = sum(1 for r in held if r["g2"]) >= 4
    print("\n=== VERDICT (held-out; pre-registered) ===")
    print(f"  G1 WARS COME FROM HUNGER      : scarce {tot_sc} vs abundant {tot_ab} raids "
          f"(x{ratio:.1f}), every-seed scarce>=abundant {all(r['g1'] for r in held)} "
          f"-> {'PASS' if g1 else 'FAIL'}")
    print(f"  G2 THE FEUD OUTLIVES FOUNDERS : {sum(1 for r in held if r['g2'])}/5 "
          f"-> {'PASS' if g2 else 'FAIL'}")
    print("\nHonest frame: G1 means the war is ECONOMICS -- lean granaries drive raids, "
          "abundance quiets them. G2 means a grievance keyed to the LAND is carried by "
          "souls who never fought the raid that made it: hatred, inherited. Together: "
          "wars that a game did not script and that outlive their soldiers.")
    sys.exit(0 if (g1 and g2) else 1)


if __name__ == "__main__":
    main()
