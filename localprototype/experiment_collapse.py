"""THE COLLAPSE FALSIFIER: does the civilization fall by ITS OWN divergence?

The civilization wheel's headline (santana_app/evolution.py): a founding people with
ONE shared view drifts apart (opinion dynamics + cultural noise), the widening rift
turns debate into grievance (agent.py rift), grievance into brawls (world/skirmish.py)
and raids (world/war.py) -- and the town collapses in on itself over what began as an
argument. That is only worth shipping if the collapse is CAUSED by the divergence,
not by hunger or the seed lottery. One pre-registered claim:

  C1 WAR-TORN BY ITS OWN SCHISM: on the SAME gentle land, with the SAME violence
      channels open (skirmish + war + the raze, both arms), a town that CAN diverge
      (opinion dynamics on, cultural noise, rift on) becomes WAR-TORN -- at some tick
      its population is <= 60% of its peak while >= 10 violent deaths (brawls + raids)
      already stand on the books -- in >= 4/5 seeds; its FROZEN twin (social graph
      frozen, zero cultural noise, rift off: divergence impossible) in <= 1/5. THE
      TWIN IS THE CONTROL: same land, same winters, same channels -- if only the town
      that can drift apart bleeds and dips, the ruin is the schism's, whatever the
      proximate cause of each death (war kills mostly by the hunger it makes: the
      raze). Tuning revisions, recorded: v1 demanded violent >= 60% of ALL deaths --
      unreachable in ANY world under welfare-capped battle deaths (the clause measured
      the wrong thing; the twin carries the control). v2 demanded pop <= 50% of peak
      -- but a fed town rebuilds through its own wars (the victor camp breeds while
      the razed camp dies; measured trough 24/44 in BOTH arms' winters), so the dip
      criterion sits at 60% WITH the violence conjunction that peace-time winters can
      never meet.

Protocol (substrate-only, MockLLM, deterministic): 24 souls founded UNITED (one belief
vector; the rift arm adds per-soul noise 0.25 -- a lean, never a camp), gentle food
(yield 1.6, rare hardship -- hunger must not author the fall), LONG lives (900-1400:
with 300-tick lives, age-death swamped every signal -- 347 natural deaths per run vs
war's capped trickle; a collapse metric needs a town whose deaths are mostly its own
doing), skirmish + war + heredity + selection + clock + lore on, rebirth off, 3000
ticks.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 251-255; C1 as above).

  python experiment_collapse.py             # TUNING ONLY -- virgin seeds stay virgin
  python experiment_collapse.py --verdict   # tuning + the held-out verdict (burns
                                            # 251-255; run ONCE, after C1 holds)
"""
from __future__ import annotations

import random
import sys

from agent import genesis as _genesis
from agent.agent import Agent
from agent.genome import express, express_social, from_agent
from services import embed
from world import regions as R
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (251, 252, 253, 254, 255)
N = 24
TICKS = 3000
COLLAPSE_POP = 0.6       # fallen well below its peak...
MIN_VIOLENT = 10         # ...with a real war on the books by then (not one brawl)


def build(seed: int, rift: bool) -> World:
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=seed)
    w.llm = __import__("services.llm", fromlist=["MockLLM"]).MockLLM(seed=7)
    w.stakes_enabled = True
    w.regions_enabled = True
    w.regions = R.Regions(seed=seed)
    w.regions.pools = [6.0] * 6
    w.war_enabled = True
    w.skirmish_enabled = True          # the violence channels are open in BOTH arms
    w.heredity_enabled = True
    w.selection_enabled = True
    w.clock_enabled = True
    w.mourning_enabled = True
    w.lore_enabled = True
    w.commons_first = True
    w.move_enabled = True              # brawls need bodies that can close
    w.bounds = (900.0, 600.0)
    w.hearing_range = 260.0            # a town SQUARE, not sealed parlours: with the
                                       # default 50 the knots become echo chambers --
                                       # deep-opposed souls never hear each other and
                                       # the rift can never fire (measured: min pair
                                       # cosine -0.37 with hostility 0.0 for 3000
                                       # ticks). Debate must carry for debate to wound.
    w.max_souls = N + 20
    w.yield_scale = 1.6                # GENTLE: hunger must not author the fall
    w.hardship_interval = 400
    # the game's HOT WHEEL knobs, both arms alike (the twin controls for all of them;
    # only divergence differs): quick births, frequent raids, and the RAZE -- a won
    # raid at open-war grudge burns what it cannot carry, so war makes the hunger
    # that makes the next war. Without the spiral, welfare-capped battle deaths are
    # a trickle no demographic collapse can ride (measured: 8 violent of 106 deaths).
    w.raze_enabled = True
    w.raid_check = 20
    w.BREED_TICKS = 30
    w.BREED_CEIL = 0.7
    w.social_genes = True              # the game's config, exactly (both arms)
    w.culture_noise = 0.18 if rift else 0.0
    base = [rng.gauss(0.0, 1.0) for _ in range(6)]
    norm = sum(v * v for v in base) ** 0.5 or 1.0
    base = [v / norm for v in base]
    for i in range(N):
        a = Agent(f"s{i}", f"F{i}", (450 + rng.uniform(-80, 80),
                                     300 + rng.uniform(-80, 80)),
                  "You are a soul.", ["the well"], w.llm, seed=1000 * seed + i,
                  temperament=rng.uniform(-0.6, 0.6), lifespan=rng.randint(900, 1400))
        _genesis.endow_faculties(a, a._rng)
        a.stance_vec = None            # one social space (see evolution.py) -- the
                                       # stance path would shadow the opinion path
        a.bond_enabled = True
        a.somatic_enabled = True
        a.rift_enabled = rift
        a.social_learning = rift       # frozen twin: the graph never moves
        a.boldness = rng.uniform(0.1, 0.9)
        a.metabolism = rng.uniform(0.2, 0.8)
        a.genome = from_agent(a, rng)
        express(a.genome, a)
        express_social(a.genome, a)    # openness -> engagement bound (the schism dial,
                                       # heritable), wrath -> rift multiplier
        if rift:
            noisy = [v + rng.gauss(0.0, 0.25) for v in base]
            nn = sum(x * x for x in noisy) ** 0.5 or 1.0
            a.belief_vec = tuple(x / nn for x in noisy)
        else:
            a.belief_vec = tuple(base)     # one view, EXACTLY -- divergence impossible
        w.add(a)
    return w


def run(seed: int, rift: bool) -> dict:
    w = build(seed, rift)
    deaths = {"violent": 0, "all": 0}
    w.bus.subscribe("skirmish_death", lambda p: deaths.__setitem__(
        "violent", deaths["violent"] + 1))
    w.bus.subscribe("war_death", lambda p: deaths.__setitem__(
        "violent", deaths["violent"] + 1))
    w.bus.subscribe("death", lambda p: deaths.__setitem__("all", deaths["all"] + 1))
    w.bus.subscribe("starvation", lambda p: deaths.__setitem__(
        "all", deaths["all"] + 1))
    peak = len(w.agents)
    collapsed = False
    trough = len(w.agents)
    for _ in range(TICKS):
        with w.lock:
            w.step(speak=True)
        pop = len(w.agents)
        peak = max(peak, pop)
        trough = min(trough, pop)
        if (not collapsed and pop <= COLLAPSE_POP * peak
                and deaths["violent"] >= MIN_VIOLENT):
            collapsed = True
    return {"collapsed": collapsed, "peak": peak, "trough": trough,
            "violent": deaths["violent"], "all_deaths": deaths["all"]}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        rf = run(seed, rift=True)
        fz = run(seed, rift=False)
        rows.append({"rift": rf["collapsed"], "frozen": fz["collapsed"]})
        print(f"seed {seed}: RIFT collapse {rf['collapsed']} "
              f"(peak {rf['peak']} trough {rf['trough']}, "
              f"violent {rf['violent']}/{rf['all_deaths']}) | "
              f"FROZEN collapse {fz['collapsed']} "
              f"(peak {fz['peak']} trough {fz['trough']}, "
              f"violent {fz['violent']}/{fz['all_deaths']})")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)")
    if "--verdict" not in sys.argv:
        print("\n(tuning only -- virgin seeds 251-255 untouched; "
              "pass --verdict to run the held-out verdict ONCE)")
        sys.exit(0)
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 251-255 (the verdict)")
    rift_n = sum(1 for r in held if r["rift"])
    froz_n = sum(1 for r in held if r["frozen"])
    ok = rift_n >= 4 and froz_n <= 1
    print("\n=== VERDICT (held-out; pre-registered) ===")
    print(f"  C1 THE FALL IS THE RIFT'S : rift-arm collapses {rift_n}/5 (need >=4), "
          f"frozen-arm {froz_n}/5 (need <=1) -> {'PASS' if ok else 'FAIL'}")
    print("\nHonest frame: PASS means the fall needs the schism -- the same land, the "
          "same open channels for violence, and only the town that could drift apart "
          "tears itself down. FAIL is recorded as the finding it is.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
